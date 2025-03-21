import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  TableContainer,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  Paper,
  FormControl,
  Select,
  MenuItem,
  FormControlLabel,
  Switch,
  CircularProgress,
  Alert,
  Box,
  Chip,
  Tooltip,
  IconButton
} from '@mui/material';
import {
  Info as InfoIcon,
  EmojiEvents as TrophyIcon,
  Speed as SpeedIcon,
  Close as CloseIcon
} from '@mui/icons-material';
import { submitRaceResult } from '../services/api';
import { League, RaceDetails } from '../types/league';

interface SubmitRaceResultsDialogProps {
  open: boolean;
  onClose: () => void;
  league: League;
  selectedRace: RaceDetails | null;
  onResultsSubmitted: (updatedLeague: League) => void;
}

interface DriverResult {
  position: number;
  fastestLap: boolean;
  dnf: boolean;
}

const SubmitRaceResultsDialog: React.FC<SubmitRaceResultsDialogProps> = ({
  open,
  onClose,
  league,
  selectedRace,
  onResultsSubmitted
}) => {
  const [raceResults, setRaceResults] = useState<Record<string, DriverResult>>({});
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [duplicatePositionWarning, setDuplicatePositionWarning] = useState(false);
  
  const standings = league.standings?.overall || {};
  const pointSystem = league.pointSystem as Record<string, number> || {};

  // Initialize race results when dialog opens with a new race
  useEffect(() => {
    if (open && selectedRace && league.participants) {
      const initialResults: Record<string, DriverResult> = {};
      league.participants.forEach((driver: any, index) => {
        // Using driver.email as the key
        const driverEmail = driver.email;
        initialResults[driverEmail] = { 
          position: index + 1, 
          fastestLap: false,
          dnf: false
        };
      });
      setRaceResults(initialResults);
      setDuplicatePositionWarning(false);
    }
  }, [open, selectedRace, league.participants]);

  // Check for duplicate positions
  useEffect(() => {
    const positions = Object.values(raceResults)
      .filter(r => !r.dnf)
      .map(r => r.position);
    
    const hasDuplicates = positions.length !== new Set(positions).size;
    setDuplicatePositionWarning(hasDuplicates);
  }, [raceResults]);

  const handlePositionChange = (driverEmail: string, position: number) => {
    setRaceResults(prev => ({
      ...prev,
      [driverEmail]: { 
        ...prev[driverEmail], 
        position,
        dnf: false // Reset DNF status when position is changed
      }
    }));
  };

  const handleDNFChange = (driverEmail: string, isDNF: boolean) => {
    setRaceResults(prev => ({
      ...prev,
      [driverEmail]: { 
        ...prev[driverEmail],
        dnf: isDNF,
        // If DNF, reset fastest lap to false
        fastestLap: isDNF ? false : prev[driverEmail].fastestLap
      }
    }));
  };

  const handleFastestLapChange = (driverEmail: string) => {
    // Update all drivers to not have fastest lap first
    const updatedResults = { ...raceResults };
    Object.keys(updatedResults).forEach(email => {
      updatedResults[email] = { ...updatedResults[email], fastestLap: false };
    });
    
    // Then set fastest lap for the selected driver (if not DNF)
    if (!updatedResults[driverEmail].dnf) {
      updatedResults[driverEmail] = { 
        ...updatedResults[driverEmail], 
        fastestLap: true 
      };
    }
    
    setRaceResults(updatedResults);
  };

  const calculatePoints = (position: number, fastestLap: boolean, dnf: boolean): number => {
    if (dnf) return 0; // No points for DNF
    
    const positionPoints = pointSystem[position.toString()] || 0;
    const fastestLapPoints = fastestLap ? league.fastestLapPoint : 0;
    return positionPoints + fastestLapPoints;
  };

  const handleSubmit = async () => {
    if (!selectedRace || !league._id) return;
    
    // Validate positions before submitting
    if (duplicatePositionWarning) {
      setError("Cannot have multiple drivers with the same position. Please resolve duplicate positions.");
      return;
    }
    
    try {
      setSubmitting(true);
      setError(null);
      
      // Format the results to match the API expectations
      const formattedResults: Record<string, { position: number; fastestLap?: boolean; points: number; dnf?: boolean }> = {};
      
      // Calculate points based on position and pointSystem
      Object.entries(raceResults).forEach(([driverEmail, result]) => {
        const { position, fastestLap, dnf } = result;
        const points = calculatePoints(position, fastestLap, dnf);
        
        formattedResults[driverEmail] = {
          position,
          points,
          ...(fastestLap && { fastestLap: true }),
          ...(dnf && { dnf: true })
        };
      });
      
      // Call API to submit race results
      const updatedLeague = await submitRaceResult(
        league._id, 
        selectedRace._id, 
        formattedResults
      );
      
      // Notify parent component
      onResultsSubmitted(updatedLeague);
      
      // Close dialog
      onClose();
      
    } catch (err: any) {
      setError(err?.response?.data?.message || 'Failed to submit race results. Please try again.');
      console.error('Error submitting race results:', err);
    } finally {
      setSubmitting(false);
    }
  };

  if (!selectedRace) return null;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
    >
      <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <TrophyIcon sx={{ mr: 1, color: 'primary.main' }} />
          Submit Race Results: {selectedRace.track}
        </Box>
        <IconButton onClick={onClose} size="small">
          <CloseIcon />
        </IconButton>
      </DialogTitle>
      <DialogContent>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}
        
        {duplicatePositionWarning && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            Warning: Multiple drivers have the same position. Each position should be unique.
          </Alert>
        )}
        
        <Box sx={{ mb: 3 }}>
          <Typography variant="body2" color="text.secondary" paragraph>
            Enter the finishing position for each driver. Mark DNF for drivers who did not finish.
            Only one driver can have the fastest lap.
          </Typography>
          
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
            <Tooltip title="Points awarded per position">
              <Box>
                <Chip
                  icon={<InfoIcon />}
                  label="Points System"
                  variant="outlined"
                  color="info"
                  size="small"
                />
              </Box>
            </Tooltip>
            {Object.entries(pointSystem)
              .sort((a, b) => Number(a[0]) - Number(b[0]))
              .map(([pos, points]) => (
                <Chip 
                  key={pos}
                  label={`P${pos}: ${points} pts`}
                  size="small"
                  variant="outlined"
                />
              ))}
            {league.fastestLapPoint > 0 && (
              <Chip 
                icon={<SpeedIcon fontSize="small" />}
                label={`Fastest Lap: ${league.fastestLapPoint} pts`}
                size="small"
                color="secondary"
              />
            )}
          </Box>
        </Box>
        
        <TableContainer component={Paper} sx={{ mt: 2 }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Driver</TableCell>
                <TableCell>Position</TableCell>
                <TableCell align="center">DNF</TableCell>
                <TableCell align="center">Fastest Lap</TableCell>
                <TableCell align="right">Points</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {league.participants && league.participants.map((driver: any) => {
                // Using driver.email as the key consistently
                const driverEmail = driver.email;
                const driverResult = raceResults[driverEmail] || { position: 0, fastestLap: false, dnf: false };
                const totalPoints = calculatePoints(
                  driverResult.position, 
                  driverResult.fastestLap, 
                  driverResult.dnf
                );
                
                return (
                  <TableRow key={driverEmail} sx={{ 
                    opacity: driverResult.dnf ? 0.7 : 1,
                    bgcolor: driverResult.fastestLap ? 'rgba(purple, 0.05)' : 'inherit'
                  }}>
                    <TableCell>
                        <Typography variant="body2" fontWeight={500}>
                            {standings[driverEmail]?.name || driver.name || driver.email}
                        </Typography>
                    </TableCell>
                    <TableCell>
                      <FormControl fullWidth size="small" disabled={driverResult.dnf}>
                        <Select
                          value={driverResult.position}
                          onChange={(e) => handlePositionChange(driverEmail, Number(e.target.value))}
                          error={duplicatePositionWarning && !driverResult.dnf}
                        >
                          {Array.from({ length: league.participants.length }, (_, i) => (
                            <MenuItem key={i+1} value={i+1}>
                              {i+1}
                            </MenuItem>
                          ))}
                        </Select>
                      </FormControl>
                    </TableCell>
                    <TableCell align="center">
                      <FormControlLabel
                        control={
                          <Switch
                            checked={driverResult.dnf}
                            onChange={(e) => handleDNFChange(driverEmail, e.target.checked)}
                            size="small"
                          />
                        }
                        label=""
                      />
                    </TableCell>
                    <TableCell align="center">
                      <FormControlLabel
                        disabled={driverResult.dnf}
                        control={
                          <Switch
                            checked={driverResult.fastestLap}
                            onChange={() => handleFastestLapChange(driverEmail)}
                            size="small"
                            color="secondary"
                          />
                        }
                        label=""
                      />
                    </TableCell>
                    <TableCell align="right">
                      <Typography 
                        variant="body2" 
                        fontWeight={totalPoints > 0 ? 'bold' : 'normal'}
                        color={totalPoints > 0 ? 'primary' : 'text.secondary'}
                      >
                        {totalPoints}
                      </Typography>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 3 }}>
        <Button 
          onClick={onClose}
          variant="outlined"
        >
          Cancel
        </Button>
        <Button 
          onClick={handleSubmit} 
          variant="contained" 
          color="primary"
          disabled={submitting || duplicatePositionWarning}
          startIcon={submitting && <CircularProgress size={20} />}
        >
          {submitting ? 'Submitting...' : 'Submit Results'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default SubmitRaceResultsDialog;