import React from "react";
import { AppBar, Toolbar, Typography, Box } from "@mui/material";
import { titleCase } from "../utils";

function Header() {
  return (
    <AppBar position="static" elevation={0}>
      <Toolbar
        sx={{
          background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
          maxWidth: "100%",
          py: 3,
        }}
      >
        <Box sx={{ flexGrow: 1 }}>
          <Typography variant="h4" component="div" sx={{ fontWeight: 700 }}>
            {titleCase("Candidate Data Transformer")}
          </Typography>
          <Typography variant="body2" sx={{ opacity: 0.95, mt: 0.8 }}>
            {titleCase("Multi-Source Candidate Data Normalization")}
          </Typography>
        </Box>
      </Toolbar>
    </AppBar>
  );
}

export default Header;
