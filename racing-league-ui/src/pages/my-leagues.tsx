import React, { useState, useEffect } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import {
  Box,
  Container,
  Paper,
  Typography,
  Card,
  CardContent,
  CircularProgress,
  Avatar,
  Chip,
  Divider,
  Button,
  IconButton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Fade,
  Alert,
  Grid,
  Tooltip,
} from '@mui/material';
import {
  Speed as SpeedIcon,
  EmojiEvents as TrophyIcon,
  MoreVert as MoreIcon,
  Add as AddIcon,
  Check as CheckIcon,
  Close as CloseIcon,
  Mail as MailIcon,
  Notifications as NotificationIcon,
} from '@mui/icons-material';
import { useAuth } from '../hooks/useAuth';
import { fetchMyLeagues, fetchMyInvites, acceptLeagueInvite, declineLeagueInvite } from '../services/api';
import { League, LeagueInvite } from '../types/league';

const MyLeagues: React.FC = () => {
  const { isAuthenticated, loading } = useAuth();
  const navigate = useNavigate();
  const [leagues, setLeagues] = useState<League[]>([]);
  const [invites, setInvites] = useState<LeagueInvite[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isInvitesLoading, setIsInvitesLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [inviteActionLoading, setInviteActionLoading] = useState<string | null>(null);

  useEffect(() => {
    const getLeagues = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const data = await fetchMyLeagues();
        setLeagues(data);
      } catch (err) {
        setError('Unable to load leagues. Please try again later.');
        console.error('Error fetching leagues:', err);
      } finally {
        setIsLoading(false);
      }
    };

    const getInvites = async () => {
      try {
        setIsInvitesLoading(true);
        const invitesData = await fetchMyInvites();
        setInvites(invitesData);
      } catch (err) {
        console.error('Error fetching invites:', err);
        // Don't show an error for invites, just show empty state
      } finally {
        setIsInvitesLoading(false);
      }
    };

    if (isAuthenticated) {
      getLeagues();
      getInvites();
    }
  }, [isAuthenticated]);

  const handleAcceptInvite = async (inviteId: string) => {
    try {
      setInviteActionLoading(inviteId);
      await acceptLeagueInvite(inviteId);
      
      // Remove from invites and refresh leagues
      setInvites(invites.filter(invite => invite._id !== inviteId));
      const updatedLeagues = await fetchMyLeagues();
      setLeagues(updatedLeagues);
    } catch (err) {
      console.error('Error accepting invite:', err);
    } finally {
      setInviteActionLoading(null);
    }
  };

  const handleDeclineInvite = async (inviteId: string) => {
    try {
      setInviteActionLoading(inviteId);
      await declineLeagueInvite(inviteId);
      
      // Remove from invites list
      setInvites(invites.filter(invite => invite._id !== inviteId));
    } catch (err) {
      console.error('Error declining invite:', err);
    } finally {
      setInviteActionLoading(null);
    }
  };

  if (loading) {
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

  if (!isAuthenticated) {
    return <Navigate to="/" />;
  }

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
        {/* Header Section */}
        <Box 
          sx={{ 
            display: 'flex',
            flexDirection: { xs: 'column', sm: 'row' },
            alignItems: 'center',
            justifyContent: 'space-between',
            mb: 4,
            gap: 2
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <Box>
              <Typography variant="h4" component="h1" sx={{ fontWeight: 600 }}>
                My Racing Leagues
              </Typography>
              <Typography color="text.secondary" variant="subtitle1">
                Manage your league memberships
              </Typography>
            </Box>
          </Box>
          
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Button 
              variant="contained" 
              color="secondary" 
              startIcon={<AddIcon />}
              onClick={() => navigate('/create-league')}
            >
              Create New League
            </Button>
            
            <Button 
              variant="contained" 
              color="primary" 
              startIcon={<AddIcon />}
              onClick={() => navigate('/search-leagues')}
            >
              Join League
            </Button>
          </Box>
        </Box>
        
        {/* Invites Section */}
        {invites.length > 0 && (
          <Box sx={{ mb: 4 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center' }}>
                <Typography variant="h5">League Invitations</Typography>
                <Chip 
                  icon={<NotificationIcon />} 
                  label={invites.length} 
                  color="secondary" 
                  size="small"
                  sx={{ ml: 2 }}
                />
              </Box>
            </Box>
            <Divider sx={{ mb: 3 }} />
            
            {isInvitesLoading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                <CircularProgress size={30} />
              </Box>
            ) : (
              <Grid container spacing={2}>
                {invites.map((invite) => (
                  <Grid item xs={12} md={6} key={invite._id}>
                    <Fade in={true}>
                      <Paper
                        sx={{
                          p: 2,
                          borderLeft: '4px solid #ff9800',
                          backgroundImage: 'linear-gradient(135deg, rgba(40,40,40,0.8) 0%, rgba(20,20,20,0.9) 100%)',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: 2
                        }}
                      >
                        <Box sx={{ display: 'flex', alignItems: 'center' }}>
                          <Avatar sx={{ bgcolor: '#ff9800', mr: 2 }}>
                            <MailIcon />
                          </Avatar>
                          <Box sx={{ flex: 1 }}>
                            <Typography variant="h6">{invite.league.name}</Typography>
                            <Typography variant="body2" color="text.secondary">
                              Invited by: {invite.inviter?.name || 'League Administrator'}
                            </Typography>
                          </Box>
                        </Box>
                        
                        <Box sx={{ display: 'flex', gap: 1, mt: 1 }}>
                          <Chip size="small" label={`${invite.league.participantsCount || 0} Members`} />
                          <Chip 
                            size="small" 
                            color="primary" 
                            label={`Status: ${invite.league.status}`} 
                          />
                        </Box>
                        
                        <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1, mt: 1 }}>
                          <Tooltip title="Decline">
                            <span>
                              <Button
                                variant="outlined"
                                color="error"
                                size="small"
                                startIcon={<CloseIcon />}
                                onClick={() => handleDeclineInvite(invite._id)}
                                disabled={inviteActionLoading === invite._id}
                              >
                                Decline
                              </Button>
                            </span>
                          </Tooltip>
                          <Tooltip title="Accept">
                            <span>
                              <Button
                                variant="contained"
                                color="success"
                                size="small"
                                startIcon={<CheckIcon />}
                                onClick={() => handleAcceptInvite(invite._id)}
                                disabled={inviteActionLoading === invite._id}
                              >
                                {inviteActionLoading === invite._id ? (
                                  <CircularProgress size={20} color="inherit" />
                                ) : (
                                  'Accept'
                                )}
                              </Button>
                            </span>
                          </Tooltip>
                        </Box>
                      </Paper>
                    </Fade>
                  </Grid>
                ))}
              </Grid>
            )}
          </Box>
        )}
        
        {/* Main Content - Leagues */}
        <Box sx={{ mb: 4 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h5">Your Memberships</Typography>
            <Chip icon={<TrophyIcon />} label={`${leagues.length} Leagues`} color="primary" variant="outlined" />
          </Box>
          <Divider sx={{ mb: 3 }} />
          
          {error && (
            <Alert severity="error" sx={{ mb: 3 }}>
              {error}
            </Alert>
          )}
          
          {isLoading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
              <CircularProgress />
            </Box>
          ) : (
            <Box>
              {leagues.length > 0 ? (
                <TableContainer component={Paper} sx={{ 
                  mb: 4, 
                  backgroundImage: 'linear-gradient(180deg, rgba(30,30,30,0.7) 0%, rgba(20,20,20,0.9) 100%)',
                }}>
                  <Table>
                    <TableHead>
                      <TableRow>
                        <TableCell>League Name</TableCell>
                        <TableCell align="center">Members</TableCell>
                        <TableCell align="center">Your Position</TableCell>
                        <TableCell align="center">Next Race</TableCell>
                        <TableCell align="center">Status</TableCell>
                        <TableCell align="right">Actions</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {leagues.map((league, index) => (
                        <Fade 
                          in={true} 
                          key={league._id}
                          style={{ transitionDelay: `${index * 50}ms` }}
                        >
                          <TableRow 
                            sx={{ 
                              '&:last-child td, &:last-child th': { border: 0 },
                              cursor: 'pointer',
                              transition: 'background-color 0.2s',
                              '&:hover': {
                                backgroundColor: 'rgba(255,255,255,0.05)'
                              }
                            }}
                            onClick={() => navigate(`/leagues/${league._id}`)}
                          >
                            <TableCell>
                              <Box sx={{ display: 'flex', alignItems: 'center' }}>
                                <Avatar sx={{ bgcolor: league.status === 'active' ? '#1e88e5' : '#757575', mr: 2, width: 40, height: 40 }}>
                                  {league.position === 1 ? <TrophyIcon color="warning" /> : <SpeedIcon />}
                                </Avatar>
                                <Typography variant="subtitle1" sx={{ fontWeight: 500 }}>
                                  {league.name}
                                </Typography>
                              </Box>
                            </TableCell>
                            <TableCell align="center">{league.participantsCount}</TableCell>
                            <TableCell align="center">
                              {league.position ? (
                                <Chip 
                                  label={`#${league.position}`} 
                                  color={league.position === 1 ? 'success' : 'default'} 
                                  size="small"
                                />
                              ) : '-'}
                            </TableCell>
                            <TableCell align="center">
                              {league.next_race !== null 
                                ? `${league.next_race.track} - ${league.next_race.date}` 
                                : league.next_race || '-'}
                            </TableCell>
                            <TableCell align="center">
                              <Chip 
                                label={league.status === 'active' ? 'Active' : 'Pending'} 
                                color={league.status === 'active' ? 'success' : 'warning'}
                                size="small"
                              />
                            </TableCell>
                            <TableCell align="right">
                              <IconButton size="small" onClick={(e) => {
                                e.stopPropagation();
                                // Handle more actions
                              }}>
                                <MoreIcon />
                              </IconButton>
                            </TableCell>
                          </TableRow>
                        </Fade>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              ) : (
                <Paper 
                  sx={{ 
                    p: 4, 
                    textAlign: 'center',
                    backgroundImage: 'linear-gradient(180deg, rgba(30,30,30,0.7) 0%, rgba(20,20,20,0.9) 100%)',
                  }}
                >
                  <Typography variant="h6" gutterBottom>No Leagues Found</Typography>
                  <Typography color="text.secondary" paragraph>
                    You haven't joined any racing leagues yet.
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center' }}>
                    <Button 
                      variant="contained" 
                      color="secondary"
                      startIcon={<AddIcon />}
                      onClick={() => navigate('/create-league')}
                    >
                      Create New League
                    </Button>
                    <Button 
                      variant="contained" 
                      color="primary"
                      startIcon={<AddIcon />}
                      onClick={() => navigate('/search-leagues')}
                    >
                      Find Leagues to Join
                    </Button>
                  </Box>
                </Paper>
              )}
            </Box>
          )}
        </Box>
        
        {/* Featured League Section - only show if there are leagues */}
        {leagues.length > 0 && !isLoading && (
          <Box>
            <Typography variant="h5" sx={{ mb: 2 }}>
              Your Top League
            </Typography>
            <Divider sx={{ mb: 3 }} />
            
            {/* Find the top league (where user has best position) */}
            {(() => {
              const topLeague = leagues
                .filter(l => l.position !== null && l.position !== undefined)
                .sort((a, b) => (a.position || 999) - (b.position || 999))[0] || leagues[0];
                
              return (
                <Card sx={{
                  backgroundImage: 'linear-gradient(135deg, rgba(30,30,30,0.8) 0%, rgba(20,20,20,0.9) 100%)',
                  borderLeft: '4px solid #1e88e5',
                  mb: 2
                }}>
                  <CardContent>
                    <Box sx={{ display: 'flex', flexDirection: { xs: 'column', md: 'row' }, justifyContent: 'space-between' }}>
                      <Box>
                        <Typography variant="h5" gutterBottom sx={{ fontWeight: 'bold', display: 'flex', alignItems: 'center' }}>
                          <TrophyIcon sx={{ mr: 1, color: 'gold' }} />
                          {topLeague.name}
                        </Typography>
                        <Typography variant="body1" sx={{ mb: 2 }}>
                          Next race: <b>
                            {topLeague.next_race && typeof topLeague.next_race === 'object' && topLeague.next_race.track
                              ? `${topLeague.next_race.track} - ${new Date(topLeague.next_race.date).toLocaleDateString()}`
                              : 'Not scheduled'}
                          </b>
                        </Typography>
                        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                          <Chip size="small" label={`${topLeague.participantsCount} Members`} />
                          <Chip size="small" color="primary" label={`Status: ${topLeague.status}`} />
                          {topLeague.position && (
                            <Chip 
                              size="small" 
                              color="success" 
                              label={`Position: #${topLeague.position}`} 
                            />
                          )}
                        </Box>
                      </Box>
                      <Box sx={{ mt: { xs: 2, md: 0 } }}>
                        <Button 
                          variant="contained" 
                          color="primary"
                          onClick={() => navigate(`/leagues/${topLeague._id}`)}
                        >
                          View Details
                        </Button>
                      </Box>
                    </Box>
                  </CardContent>
                </Card>
              );
            })()}
          </Box>
        )}
      </Container>
    </Box>
  );
};

export default MyLeagues;