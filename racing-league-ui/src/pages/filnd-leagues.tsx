import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Container,
  Paper,
  Typography,
  Avatar,
  Button,
  IconButton,
  CircularProgress,
  Alert,
  TextField,
  Grid,
  Card,
  CardContent,
  CardActions,
  CardMedia,
  InputAdornment,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Pagination,
} from '@mui/material';
import {
  Search as SearchIcon,
  ArrowBack as ArrowBackIcon,
  DirectionsCar as CarIcon,
  Group as GroupIcon,
  Public as PublicIcon,
} from '@mui/icons-material';
import { useAuth } from '../hooks/useAuth';
import { fetchPublicLeagues, joinLeague } from '../services/api';
import { League } from '../types/league';

const LeagueCard: React.FC<{
  league: League;
  onJoin: (league: League) => void;
  isUserAuthenticated: boolean;
}> = ({ league, onJoin, isUserAuthenticated }) => {
  return (
    <Card
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: 'rgba(30,30,30,0.85)',
        backgroundImage: 'linear-gradient(180deg, rgba(30,30,30,0.8) 0%, rgba(25,25,25,0.9) 100%)',
        borderRadius: 2,
        transition: 'transform 0.3s, box-shadow 0.3s',
        '&:hover': {
          transform: 'translateY(-4px)',
          boxShadow: '0 12px 20px rgba(0,0,0,0.3)',
        },
      }}
    >
      <CardMedia
        component="div"
        sx={{
          height: 140,
          backgroundColor: 'primary.dark',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <CarIcon sx={{ fontSize: 64, opacity: 0.8 }} />
      </CardMedia>
      <CardContent sx={{ flexGrow: 1 }}>
        <Typography gutterBottom variant="h5" component="h2">
          {league.name}
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
          <GroupIcon fontSize="small" sx={{ mr: 1, opacity: 0.7 }} />
          <Typography variant="body2" color="text.secondary">
            {league.participantsCount || league.participants?.length || 0} / {league.max_players} participants
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
          <PublicIcon fontSize="small" sx={{ mr: 1, opacity: 0.7 }} />
          <Typography variant="body2" color="text.secondary">
            Status: {league.status}
          </Typography>
        </Box>
        <Typography variant="body2">
          Join this racing league to compete with other drivers!
        </Typography>
        {league.next_race && (
          <Box sx={{ mt: 2 }}>
            <Typography variant="subtitle2">Next race:</Typography>
            <Typography variant="body2">
              {league.next_race.track} - {new Date(league.next_race.date).toLocaleDateString()}
            </Typography>
          </Box>
        )}
      </CardContent>
      <CardActions>
        <Button
          size="small"
          variant="contained"
          color="primary"
          onClick={() => onJoin(league)}
          fullWidth
        >
          {isUserAuthenticated ? 'Join League' : 'Sign In to Join'}
        </Button>
      </CardActions>
    </Card>
  );
};

const FindLeaguesPage: React.FC = () => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth(); // Use the hook instead of the function
  const [searchQuery, setSearchQuery] = useState('');
  const [leagues, setLeagues] = useState<League[]>([]);
  const [filteredLeagues, setFilteredLeagues] = useState<League[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [joinDialogOpen, setJoinDialogOpen] = useState(false);
  const [selectedLeague, setSelectedLeague] = useState<League | null>(null);
  const [joinInProgress, setJoinInProgress] = useState(false);
  const [page, setPage] = useState(1);
  const [message, setMessage] = useState({ type: '', text: '' });
  
  const leaguesPerPage = 9;
  
  useEffect(() => {
    const fetchLeagues = async () => {
      try {
        setIsLoading(true);
        setError(null);
        
        // Fetch public leagues regardless of authentication status
        const data = await fetchPublicLeagues();
        setLeagues(data);
        setFilteredLeagues(data);
      } catch (error) {
        setError('Failed to load leagues. Please try again later.');
      } finally {
        setIsLoading(false);
      }
    };

    fetchLeagues();
  }, []);

  // Filter leagues based on search query
  useEffect(() => {
    if (searchQuery.trim() === '') {
      setFilteredLeagues(leagues);
      return;
    }

    const query = searchQuery.toLowerCase();
    const filtered = leagues.filter(league => 
      league.name.toLowerCase().includes(query)
    );
    setFilteredLeagues(filtered);
    setPage(1);
  }, [searchQuery, leagues]);

  const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(event.target.value);
  };

  const handleJoinLeague = (league: League) => {
    // If user is not authenticated, redirect to login
    if (!isAuthenticated) {
      navigate('/login', { 
        state: { 
          from: `/search-leagues`, 
          message: 'Please sign in to join leagues',
          returnTo: `/search-leagues`
        } 
      });
      return;
    }
    
    // If authenticated, proceed with join dialog
    setSelectedLeague(league);
    setJoinDialogOpen(true);
  };

  const handleJoinConfirm = async () => {
    if (!selectedLeague || !isAuthenticated) return;
    
    setJoinInProgress(true);
    try {
      await joinLeague(selectedLeague._id);
      setMessage({ 
        type: 'success', 
        text: `Successfully joined ${selectedLeague.name}!` 
      });
      
      // Update the league in our list to show it's joined
      const updatedLeagues = leagues.map(league => 
        league._id === selectedLeague._id 
          ? { ...league, participantsCount: (league.participantsCount || 0) + 1 } 
          : league
      );
      setLeagues(updatedLeagues);
      setFilteredLeagues(
        filteredLeagues.map(league => 
          league._id === selectedLeague._id 
            ? { ...league, participantsCount: (league.participantsCount || 0) + 1 } 
            : league
        )
      );
      
      // Close dialog
      setJoinDialogOpen(false);
      
      // Navigate to the league details
      setTimeout(() => {
        navigate(`/leagues/${selectedLeague._id}`);
      }, 1500);
      
    } catch (error) {
      setMessage({
        type: 'error',
        text: 'Failed to join league. You may already be a member or the league is full.'
      });
      setJoinDialogOpen(false);
    } finally {
      setJoinInProgress(false);
    }
  };

  const handleJoinCancel = () => {
    setJoinDialogOpen(false);
    setSelectedLeague(null);
  };

  const paginatedLeagues = filteredLeagues.slice(
    (page - 1) * leaguesPerPage, 
    page * leaguesPerPage
  );

  const totalPages = Math.ceil(filteredLeagues.length / leaguesPerPage);

  if (isLoading) {
    return (
      <Box 
        sx={{
          position: 'fixed',
          top: 0,
          left: 0,
          width: '100vw',
          height: '100vh',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          backgroundColor: 'background.default',
          zIndex: 1000,
        }}
      >
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 2,
          }}
        >
          <CircularProgress color="primary" size={60} />
          <Typography variant="body1" color="text.secondary">
            Loading leagues...
          </Typography>
        </Box>
      </Box>
    );
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
        {/* Header */}
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
              onClick={() => navigate(-1)}
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
              <PublicIcon sx={{ fontSize: 36 }} />
            </Avatar>
            <Box>
              <Typography variant="h4" component="h1" sx={{ fontWeight: 600 }}>
                Find Racing Leagues
              </Typography>
              <Typography color="text.secondary" variant="subtitle1">
                Browse and join public racing leagues
              </Typography>
            </Box>
          </Box>
          
          {/* Auth status indicator */}
          {!isAuthenticated && (
            <Box sx={{ display: 'flex', gap: 2 }}>
              <Button 
                variant="outlined" 
                onClick={() => navigate('/login')}
              >
                Sign In
              </Button>
              <Button 
                variant="contained" 
                onClick={() => navigate('/login')}
              >
                Sign Up
              </Button>
            </Box>
          )}
        </Box>
        
        {/* Authentication notice for non-logged in users */}
        {!isAuthenticated && (
          <Alert 
            severity="info" 
            sx={{ mb: 4 }}
          >
            You can browse leagues without signing in, but you'll need to create an account to join them.
          </Alert>
        )}
        
        {/* Message display */}
        {message.text && (
          <Alert 
            severity={message.type === 'error' ? 'error' : 'success'} 
            sx={{ mb: 4 }}
            onClose={() => setMessage({ type: '', text: '' })}
          >
            {message.text}
          </Alert>
        )}
        
        {/* Error display */}
        {error && (
          <Alert severity="error" sx={{ mb: 4 }}>
            {error}
          </Alert>
        )}
        
        {/* Search bar */}
        <Paper
          sx={{
            p: 2,
            mb: 4,
            bgcolor: 'rgba(30,30,30,0.85)',
            backgroundImage: 'linear-gradient(180deg, rgba(30,30,30,0.8) 0%, rgba(25,25,25,0.9) 100%)',
            borderRadius: 2,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <TextField
              fullWidth
              placeholder="Search leagues by name..."
              value={searchQuery}
              onChange={handleSearchChange}
              variant="outlined"
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon />
                  </InputAdornment>
                ),
              }}
            />
          </Box>
        </Paper>
        
        {/* Results count */}
        <Box 
          sx={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center',
            mb: 2,
          }}
        >
          <Typography variant="body1">
            Found {filteredLeagues.length} {filteredLeagues.length === 1 ? 'league' : 'leagues'}
          </Typography>
        </Box>

        {/* Leagues grid */}
        {filteredLeagues.length === 0 ? (
          <Paper
            sx={{
              p: 6,
              textAlign: 'center',
              bgcolor: 'rgba(30,30,30,0.85)',
              borderRadius: 2,
            }}
          >
            <Typography variant="h6">No leagues found</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              Try adjusting your search or check back later for new leagues
            </Typography>
          </Paper>
        ) : (
          <>
            <Grid container spacing={3}>
              {paginatedLeagues.map((league) => (
                <Grid item key={league._id} xs={12} sm={6} md={4}>
                  <LeagueCard 
                    league={league} 
                    onJoin={handleJoinLeague} 
                    isUserAuthenticated={isAuthenticated}
                  />
                </Grid>
              ))}
            </Grid>
            
            {/* Pagination */}
            {totalPages > 1 && (
              <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
                <Pagination
                  count={totalPages}
                  page={page}
                  onChange={(_, value) => setPage(value)}
                  color="primary"
                  size="large"
                />
              </Box>
            )}
          </>
        )}
        
        {/* Join confirmation dialog */}
        <Dialog
          open={joinDialogOpen}
          onClose={handleJoinCancel}
        >
          <DialogTitle>Join League</DialogTitle>
          <DialogContent>
            <DialogContentText>
              Are you sure you want to join {selectedLeague?.name}?
            </DialogContentText>
          </DialogContent>
          <DialogActions>
            <Button onClick={handleJoinCancel} disabled={joinInProgress}>
              Cancel
            </Button>
            <Button 
              onClick={handleJoinConfirm} 
              variant="contained" 
              color="primary"
              disabled={joinInProgress}
            >
              {joinInProgress ? <CircularProgress size={24} /> : 'Join'}
            </Button>
          </DialogActions>
        </Dialog>
      </Container>
    </Box>
  );
};

export default FindLeaguesPage;