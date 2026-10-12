import React, { useEffect, useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  Box,
  Typography,
  Tabs,
  Tab,
  Chip,
  IconButton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Button,
  Divider,
  Avatar,
} from '@mui/material';
import {
  Close as CloseIcon,
  EmojiEvents as TrophyIcon,
  Speed as SpeedIcon,
  Flag as FlagIcon,
  Timer as TimerIcon,
  Add as AddIcon,
} from '@mui/icons-material';
import { League, RaceDetails, LeagueParticipant } from '../types/league';

interface RaceDetailDialogProps {
  open: boolean;
  onClose: () => void;
  race: RaceDetails | null;
  league: League;
  isAdmin: boolean;
  onSubmitResults: (race: RaceDetails) => void;
}

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel({ children, value, index, ...other }: TabPanelProps) {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`race-tabpanel-${index}`}
      aria-labelledby={`race-tab-${index}`}
      {...other}
    >
      {value === index && (
        <Box sx={{ pt: 3 }}>
          {children}
        </Box>
      )}
    </div>
  );
}

const RaceDetailDialog: React.FC<RaceDetailDialogProps> = ({
  open,
  onClose,
  race,
  league,
  isAdmin,
  onSubmitResults,
}) => {
  const [activeTab, setActiveTab] = useState(1);

  useEffect(() => {
    if (open) setActiveTab(1);
  }, [open, race?._id]);

  if (!race) return null;

  const isCompleted = race.status === 'Completed';
  const raceId = race._id;
  const raceResults = league.standings?.races?.[raceId] || {};
  const hasResults = Object.keys(raceResults).length > 0;
  const standings = league.standings?.overall || {};
  const pointSystem = league.pointSystem as Record<string, number> || {};

  // Build sorted results array
  const sortedResults = hasResults
    ? Object.entries(raceResults)
        .sort(([, a], [, b]) => a.position - b.position)
        .map(([driverId, result]) => {
          const participant = Array.isArray(league.participants)
            ? league.participants.find((p: LeagueParticipant) => p.email === driverId)
            : null;
          const driverName =
            participant?.league_user_name ||
            participant?.name ||
            standings[driverId]?.name ||
            participant?.email ||
            driverId;
          return {
            driverId,
            driverName,
            position: result.position,
            points: result.points,
            fastestLap: result.fastestLap || false,
          };
        })
    : [];

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: {
          bgcolor: 'rgba(30,30,30,0.95)',
          backgroundImage: 'linear-gradient(180deg, rgba(30,30,30,0.9) 0%, rgba(25,25,25,1) 100%)',
          minHeight: '60vh',
        },
      }}
    >
      {/* Header */}
      <DialogTitle
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          pb: 1,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Avatar
            sx={{
              bgcolor: isCompleted ? 'success.main' : 'primary.main',
              width: 48,
              height: 48,
            }}
          >
            <FlagIcon />
          </Avatar>
          <Box>
            <Typography variant="h5" sx={{ fontWeight: 600 }}>
              {race.track}
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
              <Typography variant="body2" color="text.secondary">
                {race.date}
              </Typography>
              <Chip
                label={race.status || 'Upcoming'}
                size="small"
                color={isCompleted ? 'success' : 'primary'}
                variant="outlined"
              />
            </Box>
          </Box>
        </Box>
        <IconButton onClick={onClose} size="small">
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <Divider />

      {/* Tabs */}
      <DialogContent sx={{ px: 3, pb: 3 }}>
        <Tabs
          value={activeTab}
          onChange={handleTabChange}
          aria-label="race detail tabs"
          indicatorColor="primary"
          textColor="primary"
          sx={{ mb: 1 }}
        >
          <Tab
            label="Qualifying"
            icon={<TimerIcon />}
            iconPosition="start"
          />
          <Tab
            label="Race"
            icon={<TrophyIcon />}
            iconPosition="start"
          />
        </Tabs>

        {/* Qualifying Tab */}
        <TabPanel value={activeTab} index={0}>
          <Paper
            sx={{
              p: 6,
              textAlign: 'center',
              bgcolor: 'rgba(0,0,0,0.2)',
              borderRadius: 2,
            }}
          >
            <TimerIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2, opacity: 0.5 }} />
            <Typography variant="h6" color="text.secondary" gutterBottom>
              Qualifying Results — Coming Soon
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Qualifying results will be available in a future update. Stay tuned!
            </Typography>
          </Paper>
        </TabPanel>

        {/* Race Tab */}
        <TabPanel value={activeTab} index={1}>
          {hasResults ? (
            <>
              {/* Points system info */}
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 3 }}>
                {Object.entries(pointSystem)
                  .sort((a, b) => Number(a[0]) - Number(b[0]))
                  .slice(0, 10)
                  .map(([pos, points]) => (
                    <Chip
                      key={pos}
                      label={`P${pos}: ${points}`}
                      size="small"
                      variant="outlined"
                    />
                  ))}
                {league.fastestLapPoint > 0 && (
                  <Chip
                    icon={<SpeedIcon fontSize="small" />}
                    label={`FL: +${league.fastestLapPoint}`}
                    size="small"
                    color="secondary"
                  />
                )}
              </Box>

              {/* Results table */}
              <TableContainer
                component={Paper}
                sx={{ bgcolor: 'rgba(0,0,0,0.2)', borderRadius: 2 }}
              >
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell sx={{ fontWeight: 700, width: 80 }}>Pos</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Driver</TableCell>
                      <TableCell align="center" sx={{ fontWeight: 700 }}>Points</TableCell>
                      <TableCell align="center" sx={{ fontWeight: 700 }}>Fastest Lap</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {sortedResults.map((result) => (
                      <TableRow
                        key={result.driverId}
                        sx={{
                          '&:last-child td, &:last-child th': { border: 0 },
                          ...(result.position <= 3 && {
                            borderLeft: `4px solid ${
                              result.position === 1
                                ? '#FFD700'
                                : result.position === 2
                                ? '#C0C0C0'
                                : '#CD7F32'
                            }`,
                          }),
                        }}
                      >
                        <TableCell>
                          <Chip
                            label={`P${result.position}`}
                            size="small"
                            color={
                              result.position === 1
                                ? 'success'
                                : result.position <= 3
                                ? 'primary'
                                : 'default'
                            }
                            sx={{ fontWeight: 600, minWidth: 48 }}
                          />
                        </TableCell>
                        <TableCell>
                          <Typography variant="body1" sx={{ fontWeight: 500 }}>
                            {result.driverName}
                          </Typography>
                        </TableCell>
                        <TableCell align="center">
                          <Typography variant="body1" sx={{ fontWeight: 600 }}>
                            {result.points}
                          </Typography>
                        </TableCell>
                        <TableCell align="center">
                          {result.fastestLap && (
                            <Chip
                              icon={<SpeedIcon fontSize="small" />}
                              label="Fastest"
                              size="small"
                              color="secondary"
                              variant="outlined"
                            />
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </>
          ) : (
            <Paper
              sx={{
                p: 6,
                textAlign: 'center',
                bgcolor: 'rgba(0,0,0,0.2)',
                borderRadius: 2,
              }}
            >
              {isAdmin ? (
                <>
                  <TrophyIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2, opacity: 0.5 }} />
                  <Typography variant="h6" color="text.secondary" gutterBottom>
                    No Results Submitted Yet
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                    Submit the race results to update the standings.
                  </Typography>
                  <Button
                    variant="contained"
                    color="warning"
                    startIcon={<AddIcon />}
                    onClick={() => onSubmitResults(race)}
                    size="large"
                  >
                    Submit Results
                  </Button>
                </>
              ) : (
                <>
                  <TrophyIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2, opacity: 0.5 }} />
                  <Typography variant="h6" color="text.secondary" gutterBottom>
                    Results Pending
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Race results haven't been submitted yet. Check back later!
                  </Typography>
                </>
              )}
            </Paper>
          )}
        </TabPanel>
      </DialogContent>
    </Dialog>
  );
};

export default RaceDetailDialog;
