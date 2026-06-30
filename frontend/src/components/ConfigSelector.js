import React, { useState } from "react";
import {
  Box,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Paper,
  Collapse,
  Button,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import ExpandLessIcon from "@mui/icons-material/ExpandLess";
import { formatJson, titleCase } from "../utils";

function ConfigSelector({ configs, selectedConfig, onConfigChange, disabled }) {
  const [showPreview, setShowPreview] = useState(false);

  const configList = Object.entries(configs).map(([name]) => ({
    name,
    label: titleCase(name.replace(/_/g, " ")),
  }));

  return (
    <Box>
      <FormControl fullWidth>
        <InputLabel>{titleCase("Select Configuration")}</InputLabel>
        <Select
          value={selectedConfig}
          label={titleCase("Select Configuration")}
          onChange={(e) => onConfigChange(e.target.value)}
          disabled={disabled}
        >
          {configList.map((config) => (
            <MenuItem key={config.name} value={config.name}>
              {config.label}
            </MenuItem>
          ))}
        </Select>
      </FormControl>

      {selectedConfig && (
        <Box sx={{ mt: 2 }}>
          <Button
            fullWidth
            onClick={() => setShowPreview(!showPreview)}
            endIcon={showPreview ? <ExpandLessIcon /> : <ExpandMoreIcon />}
            sx={{ justifyContent: "space-between" }}
          >
            {titleCase("Configuration Preview")}
          </Button>

          <Collapse in={showPreview}>
            <Paper
              variant="outlined"
              sx={{
                mt: 2,
                p: 2,
                bgcolor: "#f5f5f5",
                maxHeight: 300,
                overflow: "auto",
                fontFamily: "monospace",
                fontSize: 12,
              }}
            >
              <code style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                {formatJson(configs[selectedConfig] || {})}
              </code>
            </Paper>
          </Collapse>
        </Box>
      )}
    </Box>
  );
}

export default ConfigSelector;
