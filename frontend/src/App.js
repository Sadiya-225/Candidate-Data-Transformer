import React, { useState, useEffect } from "react";
import {
  Box,
  Container,
  Grid,
  Paper,
  Typography,
  CssBaseline,
  ThemeProvider,
  createTheme,
  Alert,
  CircularProgress,
} from "@mui/material";
import FileUploader from "./components/FileUploader";
import ConfigSelector from "./components/ConfigSelector";
import ResultsViewer from "./components/ResultsViewer";
import Header from "./components/Header";
import { getConfigs, healthCheck } from "./api";
import { titleCase } from "./utils";

const theme = createTheme({
  palette: {
    primary: {
      main: "#667eea",
    },
    secondary: {
      main: "#764ba2",
    },
    background: {
      default: "#f5f7fa",
    },
  },
  typography: {
    fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
    h1: {
      fontWeight: 600,
    },
    h2: {
      fontWeight: 600,
    },
    h3: {
      fontWeight: 600,
    },
  },
});

function App() {
  const [files, setFiles] = useState([]);
  const [configs, setConfigs] = useState({});
  const [selectedConfig, setSelectedConfig] = useState("");
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [backendError, setBackendError] = useState(false);

  useEffect(() => {
    // Check Backend Availability
    healthCheck()
      .then(() => {
        setBackendError(false);
        loadConfigs();
      })
      .catch(() => {
        setBackendError(true);
        setError(
          "Backend Server Not Available. Please Start The Backend Server.",
        );
      });
  }, []);

  const loadConfigs = async () => {
    try {
      const data = await getConfigs();
      setConfigs(data.configs || {});
      // Auto-select first config
      const firstConfig = Object.keys(data.configs || {})[0];
      if (firstConfig) {
        setSelectedConfig(firstConfig);
      }
    } catch (err) {
      setError(`Failed To Load Configurations: ${err.message}`);
    }
  };

  const handleTransform = async () => {
    if (!files.length || !selectedConfig) {
      setError("Please Select Files And A Configuration");
      return;
    }

    setLoading(true);
    setError("");
    setResults(null);

    try {
      const response = await fetch("http://localhost:5000/api/transform", {
        method: "POST",
        body: (() => {
          const formData = new FormData();
          files.forEach((file) => {
            formData.append("files", file);
          });
          formData.append("config", JSON.stringify(configs[selectedConfig]));
          return formData;
        })(),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || "Transformation Failed");
      }

      const data = await response.json();
      if (data.success) {
        setResults(data.data);
        setError("");
      } else {
        setError(titleCase(data.error || "Unknown Error"));
      }
    } catch (err) {
      setError(titleCase(err.message));
      console.error("Transformation Error:", err);
    } finally {
      setLoading(false);
    }
  };

  const downloadResults = () => {
    if (!results) return;

    const filename = `Candidates_${selectedConfig.charAt(0).toUpperCase() + selectedConfig.slice(1)}_${new Date().toISOString().split("T")[0]}.Json`;
    const dataStr = JSON.stringify(results, null, 2);
    const dataBlob = new Blob([dataStr], { type: "application/json" });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ minHeight: "100vh", bgcolor: "background.default" }}>
        <Header />

        <Container maxWidth="lg" sx={{ py: 4 }}>
          {backendError && (
            <Alert severity="error" sx={{ mb: 3 }}>
              {titleCase(
                "Backend Server Not Available. Make Sure To Run: Python Run_Web_Server.Py",
              )}
            </Alert>
          )}

          {error && (
            <Alert severity="error" sx={{ mb: 3, whiteSpace: "pre-wrap" }}>
              {error}
            </Alert>
          )}

          <Grid container spacing={3}>
            {/* Left Column: Input */}
            <Grid item xs={12} md={6}>
              <Paper elevation={2} sx={{ p: 3, height: "100%" }}>
                <Typography
                  variant="h5"
                  gutterBottom
                  sx={{ fontWeight: 600, mb: 2 }}
                >
                  📥 Upload Data
                </Typography>

                <FileUploader
                  files={files}
                  onFilesChange={setFiles}
                  disabled={loading || backendError}
                />

                <Box sx={{ mt: 3 }}>
                  <Typography
                    variant="h5"
                    gutterBottom
                    sx={{ fontWeight: 600, mb: 2 }}
                  >
                    ⚙️ Select Configuration
                  </Typography>

                  <ConfigSelector
                    configs={configs}
                    selectedConfig={selectedConfig}
                    onConfigChange={setSelectedConfig}
                    disabled={loading || backendError}
                  />
                </Box>

                <Box sx={{ mt: 3, display: "flex", gap: 2 }}>
                  <FileUploader.TransformButton
                    onClick={handleTransform}
                    disabled={
                      !files.length ||
                      !selectedConfig ||
                      loading ||
                      backendError
                    }
                    loading={loading}
                  />
                  <ResultsViewer.DownloadButton
                    onClick={downloadResults}
                    disabled={!results || loading}
                  />
                </Box>
              </Paper>
            </Grid>

            {/* Right Column: Output */}
            <Grid item xs={12} md={6}>
              <Paper elevation={2} sx={{ p: 3, height: "100%" }}>
                <Typography
                  variant="h5"
                  gutterBottom
                  sx={{ fontWeight: 600, mb: 2 }}
                >
                  📤 Results
                </Typography>

                {loading && (
                  <Box
                    sx={{
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      py: 6,
                    }}
                  >
                    <CircularProgress />
                    <Typography sx={{ mt: 2 }}>Processing...</Typography>
                  </Box>
                )}

                {!loading && !results && (
                  <Box
                    sx={{ textAlign: "center", py: 6, color: "text.secondary" }}
                  >
                    <Typography>
                      Upload Files And Click Transform To Begin
                    </Typography>
                  </Box>
                )}

                {results && !loading && <ResultsViewer data={results} />}
              </Paper>
            </Grid>
          </Grid>
        </Container>
      </Box>
    </ThemeProvider>
  );
}

export default App;
