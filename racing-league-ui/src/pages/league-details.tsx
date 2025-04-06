import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Container,
  Paper,
  Typography,
  Avatar,
  Chip,
  Divider,
  Button,
  IconButton,
  CircularProgress,
  Alert,
  Tabs,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  TextField,
  Menu,
  MenuItem,
  Grid,
  Card,
  CardContent,
  CardActions,
} from '@mui/material';
import {
  ArrowBack as ArrowBackIcon,
  Edit as EditIcon,
  Add as AddIcon,
  Flag as FlagIcon,
  EmojiEvents as TrophyIcon,
  CalendarToday as CalendarIcon,
  Settings as SettingsIcon,
  MoreVert as MoreVertIcon,
  Email as EmailIcon,
  ExitToApp as ExitIcon,
} from '@mui/icons-material';
import { useAuth } from '../hooks/useAuth';
import { fetchLeagueById, leaveLeague } from '../services/api';
import { League, RaceDetails } from '../types/league';
import SubmitRaceResultsDialog from '../components/submit-race-results';
import InvitePlayersDialog from '../components/invite-players-dialog';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`league-tabpanel-${index}`}
      aria-labelledby={`league-tab-${index}`}
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

const LeagueDetails: React.FC = () => {
  const { leagueId } = useParams<{ leagueId: string }>();
  const navigate = useNavigate();
  const { user, isAuthenticated } = useAuth();
  
  // League data state
  const [league, setLeague] = useState<League | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // UI state
  const [activeTab, setActiveTab] = useState(0);
  const [leaveLeagueDialogOpen, setLeaveLeagueDialogOpen] = useState(false);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [submitResultsDialogOpen, setSubmitResultsDialogOpen] = useState(false);
  const [selectedRace, setSelectedRace] = useState<RaceDetails | null>(null);
  const [inviteDialogOpen, setInviteDialogOpen] = useState(false);
  
  // Derived state - check if user is admin or owner
  const isAdmin = league?.admins?.includes(user?.email || '') || league?.owner === user?.email;
  const isOwner = league?.owner === user?.email;
  const menuOpen = Boolean(anchorEl);
  // Fetch league data
  useEffect(() => {
    const getLeagueDetails = async () => {
      if (!leagueId) return;
      
      try {
        setIsLoading(true);
        setError(null);
        const data = await fetchLeagueById(leagueId);
        setLeague(data);
      } catch (err) {
        setError('Unable to load league details. Please try again.');
        console.error('Error fetching league details:', err);
      } finally {
        setIsLoading(false);
      }
    };

    if (isAuthenticated && leagueId) {
      getLeagueDetails();
    }
  }, [leagueId, isAuthenticated]);

  const handleOpenSubmitDialog = (race: RaceDetails) => {
    setSelectedRace(race);
    setSubmitResultsDialogOpen(true);
  };

  const handleResultsSubmitted = (updatedLeague: League) => {
    setLeague(updatedLeague);
    setSubmitResultsDialogOpen(false);
    setSelectedRace(null);
  };

  const handleOpenInviteDialog = () => {
    setInviteDialogOpen(true);
  };

  const handleInvitesSent = () => {
    setInviteDialogOpen(false);
  };

  // Handle tab change
  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
    console.log(event);
  };
  
  // Handle menu
  const handleMenuClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };
  
  // Handle league leave
  const handleLeaveLeague = async () => {
    if (!leagueId) return;
    
    try {
      await leaveLeague(leagueId);
      navigate('/leagues');
    } catch (err) {
      console.error('Error leaving league:', err);
      setError('Failed to leave league. Please try again.');
    } finally {
      setLeaveLeagueDialogOpen(false);
    }
  };

  if (isLoading) {
    return (
      <Box 
        display="flex" 
        justifyContent="center" 
        alignItems="center" 
        minHeight="100vh"
        sx={{ backgroundColor: 'background.default' }}
      >
        <CircularProgress color="primary" size={60} />
      </Box>
    );
  }

  if (!league) {
    return (
      <Container maxWidth="md" sx={{ mt: 4 }}>
        <Alert severity="error">
          League not found or you don't have permission to view it.
        </Alert>
        <Button
          startIcon={<ArrowBackIcon />}
          sx={{ mt: 2 }}
          onClick={() => navigate('/leagues')}
        >
          Back to My Leagues
        </Button>
      </Container>
    );
  }

  // Find completed races from calendar
  const completedRaces = Array.isArray(league.calendar) 
    ? league.calendar
        .filter(race => typeof race !== 'string' && race.status === 'Completed')
        .map(race => race as RaceDetails)
    : [];

  // Get standings data from overall standings
  const standings = league.standings?.overall || {};

  return (
    <Box 
      sx={{ 
        backgroundColor: 'background.default',
        minHeight: '100vh',
        minWidth: '95vw',
        pt: 4,
        pb: 8,
        display: 'flex',
        justifyContent: 'center',
      }}
    >
      <Container maxWidth="lg">
        {/* League header */}
        <Box 
          sx={{ 
            display: 'flex',
            flexDirection: { xs: 'column', sm: 'row' },
            alignItems: { xs: 'flex-start', sm: 'center' },
            justifyContent: 'space-between',
            mb: 4
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', mb: { xs: 2, sm: 0 } }}>
            <IconButton 
              sx={{ mr: 2 }}
              onClick={() => navigate('/leagues')}
            >
              <ArrowBackIcon />
            </IconButton>
            <Avatar
              sx={{
                width: 64,
                height: 64,
                bgcolor: 'primary.main',
                mr: 2,
                boxShadow: '0 4px 12px rgba(0,0,0,0.2)'
              }}
            >
              <TrophyIcon sx={{ fontSize: 36 }} />
            </Avatar>
            <Box>
              <Box sx={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 1 }}>
                <Typography variant="h4" component="h1" sx={{ fontWeight: 600 }}>
                  {league.name}
                </Typography>
                <Chip 
                  label={league.status === 'active' ? 'Active' : 'Pending'} 
                  color={league.status === 'active' ? 'success' : 'warning'}
                  size="small"
                  sx={{ ml: 1 }}
                />
                {isAdmin && (
                  <Chip 
                    label="Admin" 
                    color="primary"
                    size="small"
                    icon={<SettingsIcon fontSize="small" />}
                  />
                )}
              </Box>
              <Typography color="text.secondary" variant="subtitle1">
                {league.participantsCount} Members 
                {/* Only show next race info if it exists */}
                {(typeof league.next_race === 'object' && league.next_race) ? 
                    ` • Next race: ${league.next_race.track} (${league.next_race.date})` : 
                    (league.next_race ? ` • ${league.next_race}` : '')
                }
              </Typography>
            </Box>
          </Box>
          
          <Box sx={{ display: 'flex', gap: 2 }}>
            {isAdmin && (
              <Button 
                variant="contained" 
                color="primary" 
                startIcon={<EmailIcon />}
                onClick={handleOpenInviteDialog}
              >
                Invite Players
              </Button>
            )}
            <IconButton
              onClick={handleMenuClick}
              aria-label="more options"
              aria-controls="league-menu"
              aria-expanded={menuOpen ? 'true' : undefined}
              aria-haspopup="true"
            >
              <MoreVertIcon />
            </IconButton>
            <Menu
              id="league-menu"
              anchorEl={anchorEl}
              open={menuOpen}
              onClose={handleMenuClose}
              MenuListProps={{
                'aria-labelledby': 'league-actions-button',
              }}
            >
              {isAdmin && [
                <MenuItem key="edit" onClick={() => {
                  handleMenuClose();
                  // Navigate to edit page or open edit dialog
                }}>
                  <EditIcon fontSize="small" sx={{ mr: 1 }} />
                  Edit League
                </MenuItem>,
                <Divider key="divider" />
              ]}
              <MenuItem onClick={() => {
                handleMenuClose();
                setLeaveLeagueDialogOpen(true);
              }} sx={{ color: 'error.main' }}>
                <ExitIcon fontSize="small" sx={{ mr: 1 }} />
                Leave League
              </MenuItem>
            </Menu>
          </Box>
        </Box>
        
        {/* League tabs & content */}
        <Paper 
          sx={{ 
            bgcolor: 'rgba(30,30,30,0.85)',
            backgroundImage: 'linear-gradient(180deg, rgba(30,30,30,0.8) 0%, rgba(25,25,25,0.9) 100%)',
            borderRadius: 2,
            overflow: 'hidden',
            mb: 4
          }}
        >
          <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
            <Tabs
              value={activeTab}
              onChange={handleTabChange}
              aria-label="league details tabs"
              indicatorColor="primary"
              textColor="primary"
              variant="scrollable"
              scrollButtons="auto"
            >
              <Tab label="Overview" icon={<TrophyIcon />} iconPosition="start" />
              <Tab label="Standings" icon={<FlagIcon />} iconPosition="start" />
              <Tab label="Calendar" icon={<CalendarIcon />} iconPosition="start" />
              {isAdmin && <Tab label="Settings" icon={<SettingsIcon />} iconPosition="start" />}
            </Tabs>
          </Box>
          
          {/* Overview Tab */}
          <TabPanel value={activeTab} index={0}>
            <Box sx={{ p: 3 }}>
              {error && <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert>}
              
              <Grid container spacing={4}>
                <Grid item xs={12} md={8}>
                  <Typography variant="h5" gutterBottom>League Overview</Typography>
                  <Divider sx={{ mb: 2 }} />
                  
                  <Box sx={{ mb: 4 }}>
                    <Typography variant="h6" gutterBottom>Recent Results</Typography>
                    <TableContainer component={Paper} sx={{ mb: 2, bgcolor: 'rgba(0,0,0,0.2)' }}>
                      {completedRaces.length > 0 ? (
                        <Table size="small">
                          <TableHead>
                            <TableRow>
                              <TableCell>Race</TableCell>
                              <TableCell>Date</TableCell>
                              <TableCell>Winner</TableCell>
                              <TableCell>Status</TableCell>
                            </TableRow>
                          </TableHead>
                          <TableBody>
                            {completedRaces.map((race, index) => (
                              <TableRow key={index}>
                                <TableCell>{race.track}</TableCell>
                                <TableCell>{race.date}</TableCell>
                                <TableCell>
                                  {/* Winner would need to be determined from standings data */}
                                  {league.standings.races[race.track] ? 
                                    Object.entries(league.standings.races[race.track])
                                      .find(([_, result]) => result.position === 1)?.[0] || 'Unknown' : 
                                    'No results'
                                  }
                                </TableCell>
                                <TableCell>{race.status}</TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      ) : (
                        <Box sx={{ p: 3, textAlign: 'center' }}>
                          <Typography color="text.secondary">
                            No race results have been recorded yet.
                          </Typography>
                        </Box>
                      )}
                    </TableContainer>
                    
                    {isAdmin && (
                      <Button 
                        variant="outlined" 
                        color="primary"
                        startIcon={<AddIcon />}
                        size="small"
                      >
                        Add Race Result
                      </Button>
                    )}
                  </Box>
                  
                  <Box sx={{ mb: 4 }}>
                    <Typography variant="h6" gutterBottom>Top Drivers</Typography>
                    <TableContainer component={Paper} sx={{ bgcolor: 'rgba(0,0,0,0.2)' }}>
                      {Object.keys(standings).length > 0 ? (
                        <Table size="small">
                          <TableHead>
                            <TableRow>
                              <TableCell>Position</TableCell>
                              <TableCell>Driver</TableCell>
                              <TableCell>Points</TableCell>
                              <TableCell>Wins</TableCell>
                            </TableRow>
                          </TableHead>
                          <TableBody>
                            {Object.entries(standings)
                              .sort(([,a], [,b]) => (b.points - a.points))
                              .slice(0, 5)
                              .map(([driverId, stats], index) => (
                                <TableRow key={driverId}>
                                  <TableCell>
                                    <Chip 
                                      label={`#${index + 1}`} 
                                      color={index === 0 ? 'success' : 'default'} 
                                      size="small" 
                                    />
                                  </TableCell>
                                  <TableCell>{stats.name || driverId}</TableCell>
                                  <TableCell>{stats.points}</TableCell>
                                  <TableCell>{stats.wins}</TableCell>
                                </TableRow>
                              ))}
                          </TableBody>
                        </Table>
                      ) : (
                        <Box sx={{ p: 3, textAlign: 'center' }}>
                          <Typography color="text.secondary">
                            No standings information available yet.
                          </Typography>
                        </Box>
                      )}
                    </TableContainer>
                  </Box>
                </Grid>
                
                <Grid item xs={12} md={4}>
                  <Typography variant="h5" gutterBottom>League Information</Typography>
                  <Divider sx={{ mb: 2 }} />
                  
                  <Paper sx={{ p: 2, mb: 3, bgcolor: 'rgba(0,0,0,0.2)' }}>
                    <Typography variant="subtitle2" color="text.secondary">League Type</Typography>
                    <Typography variant="body1" sx={{ mb: 2 }}>
                      {league.public ? 'Public' : 'Private'} League
                    </Typography>
                    
                    <Typography variant="subtitle2" color="text.secondary">Members</Typography>
                    <Typography variant="body1" sx={{ mb: 2 }}>
                      {league.participantsCount} / {league.max_players} Members
                    </Typography>
                    
                    <Typography variant="subtitle2" color="text.secondary">Created</Typography>
                    <Typography variant="body1" sx={{ mb: 2 }}>
                      {new Date(league.created_at).toLocaleDateString()}
                    </Typography>
                    
                    <Typography variant="subtitle2" color="text.secondary">Point System</Typography>
                    <Typography variant="body1" sx={{ mb: 1 }}>
                      {league.fastestLapPoint > 0 ? 
                        `Standard F1 + ${league.fastestLapPoint} for fastest lap` :
                        'Standard F1 points'}
                    </Typography>
                  </Paper>
                  
                  <Typography variant="h6" gutterBottom>Next Race</Typography>
                    <Card sx={{ mb: 3, bgcolor: 'rgba(0,0,0,0.2)' }}>
                    <CardContent>
                        {league.next_race !== null ? (
                        <>
                            <Typography variant="h6" gutterBottom>{league.next_race?.track}</Typography>
                            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                            {league.next_race?.date}
                            </Typography>
                        </>
                        ) : (
                            <Typography variant="body2" color="text.secondary">
                            No upcoming races
                            </Typography>
                        )
                        }
                    </CardContent>
                    {isAdmin && (
                        <CardActions>
                        <Button size="small">
                            {league.next_race ? 'Edit' : 'Add Race'}
                        </Button>
                        </CardActions>
                    )}
                </Card>
                </Grid>
              </Grid>
            </Box>
          </TabPanel>
          
          {/* Standings Tab */}
          <TabPanel value={activeTab} index={1}>
            <Box sx={{ p: 3 }}>
              <Typography variant="h5" gutterBottom>Championship Standings</Typography>
              <Divider sx={{ mb: 3 }} />
              
              <TableContainer component={Paper} sx={{ bgcolor: 'rgba(0,0,0,0.2)' }}>
                {Object.keys(standings).length > 0 ? (
                  <Table>
                    <TableHead>
                      <TableRow>
                        <TableCell>Position</TableCell>
                        <TableCell>Driver</TableCell>
                        <TableCell align="center">Points</TableCell>
                        <TableCell align="center">Wins</TableCell>
                        <TableCell align="center">Podiums</TableCell>
                        <TableCell align="center">DNFs</TableCell>
                        <TableCell align="center">Fastest Laps</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {Object.entries(standings)
                        .sort(([,a], [,b]) => (b.points - a.points))
                        .map(([driverId, stats], index) => (
                          <TableRow key={driverId}>
                            <TableCell>
                              <Chip 
                                label={`#${index + 1}`} 
                                color={index === 0 ? 'success' : 'default'}
                                size="small" 
                              />
                            </TableCell>
                            <TableCell>{stats.name || driverId}</TableCell>
                            <TableCell align="center">{stats.points}</TableCell>
                            <TableCell align="center">{stats.wins}</TableCell>
                            <TableCell align="center">{stats.podiums}</TableCell>
                            <TableCell align="center">{stats.dnfs}</TableCell>
                            <TableCell align="center">{stats.fastestLaps}</TableCell>
                          </TableRow>
                        ))}
                    </TableBody>
                  </Table>
                ) : (
                  <Box sx={{ p: 4, textAlign: 'center' }}>
                    <Typography variant="h6" color="text.secondary" gutterBottom>
                      No Standings Available
                    </Typography>
                    <Typography color="text.secondary">
                      Standings will appear after race results are added.
                    </Typography>
                  </Box>
                )}
              </TableContainer>
            </Box>
          </TabPanel>
          
          {/* Calendar Tab */}
          <TabPanel value={activeTab} index={2}>
            <Box sx={{ p: 3 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="h5">Race Calendar</Typography>
                {isAdmin && (
                  <Button 
                    variant="contained" 
                    color="primary"
                    startIcon={<AddIcon />}
                    size="small"
                  >
                    Add Race
                  </Button>
                )}
              </Box>
              <Divider sx={{ mb: 3 }} />
              
              <Grid container spacing={2}>
                {Array.isArray(league.calendar) && league.calendar.length > 0 ? (
                  league.calendar.map((race, index) => (
                    <Grid item xs={12} md={6} key={index}>
                      <Card sx={{ mb: 2, bgcolor: 'rgba(0,0,0,0.2)' }}>
                        <CardContent>
                          <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                            <Typography variant="h6">
                              {typeof race === 'string' ? race : race.track}
                            </Typography>
                            {typeof race !== 'string' && (
                              <Chip 
                                label={race.status || "Upcoming"} 
                                size="small" 
                                color={race.status === "Completed" ? "default" : "primary"} 
                              />
                            )}
                          </Box>
                          {typeof race !== 'string' && (
                            <Typography variant="body2" color="text.secondary">
                              {race.date}
                            </Typography>
                          )}
                        </CardContent>
                        {isAdmin && (
                        <CardActions>
                            <Button size="small">Edit</Button>
                            {typeof race !== 'string' && race.status !== 'Completed' && (
                            <Button 
                                size="small"
                                color="warning"
                                onClick={() => handleOpenSubmitDialog(race as RaceDetails)}
                            >
                                Submit Results
                            </Button>
                            )}
                        </CardActions>
                        )}
                      </Card>
                    </Grid>
                  ))
                ) : (
                  <Grid item xs={12}>
                    <Paper sx={{ p: 4, textAlign: 'center', bgcolor: 'rgba(0,0,0,0.2)' }}>
                      <Typography variant="h6" color="text.secondary" gutterBottom>
                        No Races Scheduled
                      </Typography>
                      <Typography color="text.secondary" paragraph>
                        The race calendar for this league is empty.
                      </Typography>
                      {isAdmin && (
                        <Button 
                          variant="contained" 
                          color="primary"
                          startIcon={<AddIcon />}
                        >
                          Create First Race
                        </Button>
                      )}
                    </Paper>
                  </Grid>
                )}
              </Grid>
            </Box>
          </TabPanel>
          
          {/* Settings Tab (Admin Only) */}
          {isAdmin && (
            <TabPanel value={activeTab} index={3}>
              <Box sx={{ p: 3 }}>
                <Typography variant="h5" gutterBottom>League Settings</Typography>
                <Divider sx={{ mb: 3 }} />
                
                <Grid container spacing={3}>
                  <Grid item xs={12} md={6}>
                    <Typography variant="h6" gutterBottom>General Settings</Typography>
                    <Paper sx={{ p: 2, mb: 3, bgcolor: 'rgba(0,0,0,0.2)' }}>
                      <TextField
                        label="League Name"
                        fullWidth
                        margin="normal"
                        defaultValue={league.name}
                      />
                      
                      <TextField
                        label="Maximum Players"
                        type="number"
                        fullWidth
                        margin="normal"
                        defaultValue={league.max_players}
                      />
                      
                      <TextField
                        label="Points for Fastest Lap"
                        type="number"
                        fullWidth
                        margin="normal"
                        defaultValue={league.fastestLapPoint}
                      />
                      
                      <Box sx={{ mt: 2, display: 'flex', justifyContent: 'flex-end' }}>
                        <Button variant="contained" color="primary">
                          Save Settings
                        </Button>
                      </Box>
                    </Paper>
                  </Grid>
                  
                  <Grid item xs={12} md={6}>
                    <Typography variant="h6" gutterBottom>Admin Actions</Typography>
                    <Paper sx={{ p: 2, bgcolor: 'rgba(0,0,0,0.2)' }}>
                      <Button
                        fullWidth
                        variant="outlined"
                        color="primary"
                        sx={{ mb: 2 }}
                      >
                        Manage Admins
                      </Button>
                      
                      <Button
                        fullWidth
                        variant="outlined"
                        color="primary"
                        sx={{ mb: 2 }}
                      >
                        Manage Members
                      </Button>
                      
                      {isOwner && (
                        <Button
                          fullWidth
                          variant="outlined"
                          color="error"
                        >
                          Delete League
                        </Button>
                      )}
                    </Paper>
                  </Grid>
                </Grid>
              </Box>
            </TabPanel>
          )}
        </Paper>
      </Container>
      
      {/* Leave League Dialog */}
      <Dialog
        open={leaveLeagueDialogOpen}
        onClose={() => setLeaveLeagueDialogOpen(false)}
      >
        <DialogTitle>Leave League?</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to leave "{league.name}"? You'll lose your position in the standings.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setLeaveLeagueDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleLeaveLeague} color="error" variant="contained">
            Leave League
          </Button>
        </DialogActions>
      </Dialog>
      <SubmitRaceResultsDialog
        open={submitResultsDialogOpen}
        onClose={() => setSubmitResultsDialogOpen(false)}
        league={league}
        selectedRace={selectedRace}
        onResultsSubmitted={handleResultsSubmitted}
      />
      <InvitePlayersDialog
        open={inviteDialogOpen}
        leagueId={leagueId || ''}
        leagueName={league?.name || ''}
        onClose={() => setInviteDialogOpen(false)}
        onInvitesSent={handleInvitesSent}
      />
    </Box>
  );
};

export default LeagueDetails;