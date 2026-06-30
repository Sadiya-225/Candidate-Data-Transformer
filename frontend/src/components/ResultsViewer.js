import React, { useState } from 'react';
import {
  Box,
  Button,
  Paper,
  Typography,
  Tabs,
  Tab,
  Collapse,
  Card,
  CardContent,
  Grid,
} from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import { formatJson, titleCase } from '../utils';

function TabPanel(props) {
  const { children, value, index, ...other } = props;
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`tabpanel-${index}`}
      aria-labelledby={`tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ py: 2 }}>{children}</Box>}
    </div>
  );
}

function ResultsViewer({ data }) {
  const [tabValue, setTabValue] = useState(0);
  const [expandedIndex, setExpandedIndex] = useState(null);

  const handleTabChange = (event, newValue) => {
    setTabValue(newValue);
  };

  const toggleExpand = (index) => {
    setExpandedIndex(expandedIndex === index ? null : index);
  };

  return (
    <Box>
      <Tabs value={tabValue} onChange={handleTabChange} sx={{ mb: 2 }}>
        <Tab label={titleCase('Json View')} id="tab-0" />
        <Tab label={titleCase('Card View')} id="tab-1" />
        <Tab label={titleCase('Statistics')} id="tab-2" />
      </Tabs>

      {/* JSON View */}
      <TabPanel value={tabValue} index={0}>
        <Paper
          variant="outlined"
          sx={{
            p: 2,
            bgcolor: '#f5f5f5',
            maxHeight: 500,
            overflow: 'auto',
            fontFamily: 'monospace',
            fontSize: 12,
          }}
        >
          <code style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
            {titleCase(formatJson(data))}
          </code>
        </Paper>
      </TabPanel>

      {/* Card View */}
      <TabPanel value={tabValue} index={1}>
        <Grid container spacing={2}>
          {Array.isArray(data)
            ? data.map((candidate, index) => (
              <Grid item xs={12} key={index}>
                <Card>
                  <CardContent>
                    <Box
                      sx={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        cursor: 'pointer',
                      }}
                      onClick={() => toggleExpand(index)}
                    >
                      <Typography variant="h6" sx={{ fontWeight: 600 }}>
                        {titleCase(candidate.full_name || `Candidate ${index + 1}`)}
                      </Typography>
                      {expandedIndex === index ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                    </Box>

                    <Collapse in={expandedIndex === index}>
                      <Box sx={{ mt: 2, pt: 2, borderTop: '1px solid #eee' }}>
                        {candidate.emails && (
                          <Typography variant="body2">
                            <strong>{titleCase('Emails')}:</strong>{' '}
                            {titleCase(candidate.emails.join(', '))}
                          </Typography>
                        )}
                        {candidate.phones && (
                          <Typography variant="body2">
                            <strong>{titleCase('Phones')}:</strong>{' '}
                            {titleCase(candidate.phones.join(', '))}
                          </Typography>
                        )}
                        {candidate.overall_confidence && (
                          <Typography variant="body2">
                            <strong>{titleCase('Confidence')}:</strong>{' '}
                            {(candidate.overall_confidence * 100).toFixed(1)}%
                          </Typography>
                        )}
                        {candidate.skills && candidate.skills.length > 0 && (
                          <Typography variant="body2">
                            <strong>{titleCase('Skills')}:</strong>{' '}
                            {titleCase(
                              candidate.skills
                                .map(skill => typeof skill === 'string' ? skill : skill.name)
                                .join(', ')
                            )}
                          </Typography>
                        )}
                      </Box>
                    </Collapse>
                  </CardContent>
                </Card>
              </Grid>
            ))
            : Object.entries(data).map(([key, value], index) => (
              <Grid item xs={12} key={index}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" sx={{ fontWeight: 600 }}>
                      {titleCase(key)}
                    </Typography>
                    <Typography variant="body2" sx={{ mt: 1 }}>
                      {titleCase(JSON.stringify(value))}
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
            ))}
        </Grid>
      </TabPanel>

      {/* Statistics */}
      <TabPanel value={tabValue} index={2}>
        <Grid container spacing={2}>
          <Grid item xs={12} sm={6}>
            <Card>
              <CardContent>
                <Typography color="textSecondary" gutterBottom>
                  {titleCase('Total Records')}
                </Typography>
                <Typography variant="h5">{Array.isArray(data) ? data.length : 1}</Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6}>
            <Card>
              <CardContent>
                <Typography color="textSecondary" gutterBottom>
                  {titleCase('Average Confidence')}
                </Typography>
                <Typography variant="h5">
                  {Array.isArray(data) && data.length > 0
                    ? (
                      (data.reduce((sum, d) => sum + (d.overall_confidence || 0), 0) /
                        data.length) *
                      100
                    ).toFixed(1)
                    : 'N/A'}
                  %
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </TabPanel>
    </Box>
  );
}

export function DownloadButton({ onClick, disabled }) {
  return (
    <Button
      variant="contained"
      color="success"
      fullWidth
      onClick={onClick}
      disabled={disabled}
      startIcon={<DownloadIcon />}
      sx={{ py: 1.5, fontWeight: 600 }}
    >
      {titleCase('Download Json')}
    </Button>
  );
}

ResultsViewer.DownloadButton = DownloadButton;

export default ResultsViewer;
