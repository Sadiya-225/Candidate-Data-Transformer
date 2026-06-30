import React from "react";
import {
  Box,
  Button,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
  Typography,
  CircularProgress,
  Paper,
} from "@mui/material";
import DeleteIcon from "@mui/icons-material/Delete";
import CloudUploadIcon from "@mui/icons-material/CloudUpload";
import { useDropzone } from "react-dropzone";
import { formatFileSize, titleCase } from "../utils";

function FileUploader({ files, onFilesChange, disabled }) {
  const onDrop = (acceptedFiles) => {
    onFilesChange([...files, ...acceptedFiles]);
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "text/csv": [".csv"],
      "application/json": [".json"],
      "application/pdf": [".pdf"],
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        [".docx"],
      "text/plain": [".txt"],
    },
    disabled,
  });

  const handleRemoveFile = (index) => {
    onFilesChange(files.filter((_, i) => i !== index));
  };

  return (
    <Box>
      <Paper
        {...getRootProps()}
        sx={{
          p: 3,
          textAlign: "center",
          border: "2px dashed",
          borderColor: isDragActive ? "primary.main" : "divider",
          bgcolor: isDragActive ? "action.hover" : "background.paper",
          cursor: disabled ? "not-allowed" : "pointer",
          transition: "all 0.3s",
          opacity: disabled ? 0.5 : 1,
          "&:hover": {
            borderColor: disabled ? "divider" : "primary.main",
            bgcolor: disabled ? "background.paper" : "action.hover",
          },
        }}
      >
        <input {...getInputProps()} />
        <CloudUploadIcon sx={{ fontSize: 48, color: "primary.main", mb: 1 }} />
        <Typography variant="body1" gutterBottom>
          {isDragActive
            ? titleCase("Drop Files Here")
            : titleCase("Drag Files Here Or Click To Select")}
        </Typography>
        <Typography variant="caption" color="textSecondary">
          {"Supported: csv, json, pdf, docx, txt"}
        </Typography>
      </Paper>

      {files.length > 0 && (
        <Box sx={{ mt: 2 }}>
          <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: 600 }}>
            {titleCase("Selected Files")} ({files.length})
          </Typography>
          <List dense>
            {files.map((file, index) => (
              <ListItem
                key={index}
                sx={{ bgcolor: "action.hover", mb: 0.5, borderRadius: 1 }}
              >
                <ListItemText
                  primary={file.name}
                  secondary={formatFileSize(file.size)}
                />
                <ListItemSecondaryAction>
                  <IconButton
                    edge="end"
                    size="small"
                    onClick={() => handleRemoveFile(index)}
                    disabled={disabled}
                  >
                    <DeleteIcon />
                  </IconButton>
                </ListItemSecondaryAction>
              </ListItem>
            ))}
          </List>
        </Box>
      )}
    </Box>
  );
}

export function TransformButton({ onClick, disabled, loading }) {
  return (
    <Button
      variant="contained"
      color="primary"
      fullWidth
      onClick={onClick}
      disabled={disabled}
      sx={{ py: 1.5, fontWeight: 600 }}
    >
      {loading ? (
        <>
          <CircularProgress size={20} sx={{ mr: 1 }} />
          {titleCase("Processing")}
        </>
      ) : (
        titleCase("Transform Data")
      )}
    </Button>
  );
}

FileUploader.TransformButton = TransformButton;

export default FileUploader;
