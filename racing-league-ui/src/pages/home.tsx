import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Container,
  Typography,
  Button,
  Grid,
  Card,
  CardContent,
  AppBar,
  Toolbar,
  useTheme,
  useMediaQuery,
  Paper,
  Avatar,
  Chip,
} from '@mui/material';
import {
  DirectionsCar as CarIcon,
  EmojiEvents as TrophyIcon,
  Group as GroupIcon,
  Timeline as TimelineIcon,
  Leaderboard as LeaderboardIcon,
  BarChart as StatsIcon,
  CalendarToday as CalendarIcon,
  Star as StarIcon,
  ArrowForward as ArrowForwardIcon,
  Login as LoginIcon,
  PersonAdd as SignUpIcon,
} from '@mui/icons-material';
import { useAuth } from '../hooks/useAuth';

const backgroundImage = 'login_background.png'; 

const Home: React.FC = () => {
  const navigate = useNavigate();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const { isAuthenticated } = useAuth();

  const features = [
    {
      icon: <TrophyIcon sx={{ fontSize: 48, color: 'gold' }} />,
      title: 'Create Racing Leagues',
      description: 'Set up your own racing championship with custom rules, point systems, and race calendars.',
      highlight: 'Complete Control'
    },
    {
      icon: <LeaderboardIcon sx={{ fontSize: 48, color: '#0088ff' }} />,
      title: 'Track Standings',
      description: 'Real-time championship standings, race results, and detailed driver statistics.',
      highlight: 'Live Updates'
    },
    {
      icon: <GroupIcon sx={{ fontSize: 48, color: '#00cc88' }} />,
      title: 'Team Management',
      description: 'Invite friends, manage participants, and organize your racing community.',
      highlight: 'Social Racing'
    },
    {
      icon: <CalendarIcon sx={{ fontSize: 48, color: '#ff6600' }} />,
      title: 'Race Calendar',
      description: 'Schedule races, manage events, and keep everyone informed about upcoming competitions.',
      highlight: 'Easy Scheduling'
    },
    {
      icon: <StatsIcon sx={{ fontSize: 48, color: '#9c27b0' }} />,
      title: 'Detailed Analytics',
      description: 'Comprehensive statistics, performance tracking, and historical race data.',
      highlight: 'Data Insights'
    },
    {
      icon: <TimelineIcon sx={{ fontSize: 48, color: '#f44336' }} />,
      title: 'Season Progress',
      description: 'Follow championship progression, view race history, and track achievements.',
      highlight: 'Full History'
    },
  ];

  const handleGetStarted = () => {
    if (isAuthenticated) {
      navigate('/dashboard');
    } else {
      navigate('/login');
    }
  };

  return (
    <Box sx={{ 
        minHeight: '100vh', 
        minWidth: '100vw', 
        bgcolor: 'background.default',
        backgroundImage: `url(${backgroundImage})`,
        backgroundSize: 'cover',
        backgroundColor: 'rgba(0, 0, 0, 0.7)', // Fallback color
        backgroundPosition: 'center',
        backgroundRepeat: 'no-repeat',
        backgroundAttachment: 'fixed',
        }}>
      {/* Navigation Header */}
      <AppBar 
        position="static" 
        sx={{ 
          bgcolor: 'transparent',
          boxShadow: 'none',
          borderBottom: '1px solid rgba(255,255,255,0.1)'
        }}
      >
        <Toolbar>
          <Box sx={{ display: 'flex', alignItems: 'center', flexGrow: 1 }}>
            <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
              Racing League Manager
            </Typography>
          </Box>
          
          {!isAuthenticated && (
            <Box sx={{ display: 'flex', gap: 2 }}>
              <Button 
                color="inherit" 
                onClick={() => navigate('/login')}
                startIcon={<LoginIcon />}
              >
                Sign In
              </Button>
              <Button 
                variant="contained" 
                color="primary"
                onClick={() => navigate('/login')}
                startIcon={<SignUpIcon />}
              >
                Get Started
              </Button>
            </Box>
          )}
          
          {isAuthenticated && (
            <Button 
              variant="contained" 
              color="primary"
              onClick={() => navigate('/dashboard')}
            >
              Go to Dashboard
            </Button>
          )}
        </Toolbar>
      </AppBar>

      {/* Hero Section */}
      <Container maxWidth="lg" sx={{ py: 8 }}>
        <Grid container spacing={4} alignItems="center">
          <Grid item xs={12} md={6}>
            <Typography 
              variant={isMobile ? "h3" : "h2"} 
              component="h1" 
              sx={{ 
                fontWeight: 700, 
                mb: 3,
                background: 'linear-gradient(45deg, #2196F3 30%, #21CBF3 90%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
              }}
            >
              Organize Racing Leagues Like a Pro
            </Typography>
            
            <Typography 
              variant="h5" 
              sx={{ 
                mb: 4, 
                color: 'text.secondary',
                lineHeight: 1.6
              }}
            >
              Create, manage, and track competitive racing leagues with friends. 
              Real-time standings, race scheduling, and detailed analytics all in one place.
            </Typography>
            
            <Box sx={{ display: 'flex', flexDirection: isMobile ? 'column' : 'row', gap: 2, mb: 4 }}>
              <Button 
                variant="contained" 
                color="primary" 
                size="large"
                onClick={handleGetStarted}
                endIcon={<ArrowForwardIcon />}
                sx={{ py: 1.5, px: 4 }}
              >
                {isAuthenticated ? 'Go to Dashboard' : 'Start Your League'}
              </Button>
              
              {!isAuthenticated && (
                <Button 
                  variant="outlined" 
                  size="large"
                  onClick={() => navigate('/find-leagues')}
                  sx={{ py: 1.5, px: 4 }}
                >
                  Explore Public Leagues
                </Button>
              )}
            </Box>
            
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <Typography variant="body2" color="text.secondary">
                Trusted by racing communities worldwide
              </Typography>
              <Box sx={{ display: 'flex', gap: 0.5 }}>
                {[1, 2, 3, 4, 5].map((star) => (
                  <StarIcon key={star} sx={{ fontSize: 16, color: 'gold' }} />
                ))}
              </Box>
            </Box>
          </Grid>
          
          <Grid item xs={12} md={6}>
            <Paper 
              elevation={8}
              sx={{ 
                p: 4, 
                background: 'linear-gradient(145deg, rgba(30,30,30,0.9), rgba(20,20,20,0.95))',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: 3,
                position: 'relative',
                overflow: 'hidden'
              }}
            >
              <Box sx={{ position: 'relative', zIndex: 2 }}>
                <Typography variant="h6" sx={{ mb: 2, color: 'primary.main' }}>
                  Championship Standings
                </Typography>
                
                {/* Mock leaderboard */}
                {['Driver A', 'Driver B', 'Driver C'].map((driver, index) => (
                  <Box 
                    key={driver}
                    sx={{ 
                      display: 'flex', 
                      alignItems: 'center', 
                      mb: 2, 
                      p: 1.5,
                      bgcolor: 'rgba(255,255,255,0.05)',
                      borderRadius: 1,
                      border: index === 0 ? '1px solid gold' : '1px solid rgba(255,255,255,0.1)'
                    }}
                  >
                    <Typography 
                      variant="h6" 
                      sx={{ 
                        mr: 2, 
                        minWidth: 24,
                        color: index === 0 ? 'gold' : 'text.primary'
                      }}
                    >
                      {index + 1}
                    </Typography>
                    <Avatar sx={{ mr: 2, bgcolor: 'primary.main' }}>
                      {driver.charAt(0)}
                    </Avatar>
                    <Box sx={{ flexGrow: 1 }}>
                      <Typography variant="body1">{driver}</Typography>
                      <Typography variant="body2" color="text.secondary">
                        {100 - index * 15} points
                      </Typography>
                    </Box>
                    {index === 0 && <TrophyIcon sx={{ color: 'gold' }} />}
                  </Box>
                ))}
                
                <Chip 
                  label="Live Updates" 
                  color="primary" 
                  size="small" 
                  sx={{ mt: 1 }}
                />
              </Box>
              
              {/* Decorative background */}
              <Box
                sx={{
                  position: 'absolute',
                  top: -50,
                  right: -50,
                  width: 100,
                  height: 100,
                  opacity: 0.1,
                  transform: 'rotate(15deg)',
                }}
              >
                <CarIcon sx={{ fontSize: 100 }} />
              </Box>
            </Paper>
          </Grid>
        </Grid>
      </Container>

      {/* Features Section */}
      <Container maxWidth="lg" sx={{ py: 8 }}>
        <Typography 
          variant="h3" 
          align="center" 
          sx={{ mb: 2, fontWeight: 600 }}
        >
          Everything You Need to Run Racing Leagues
        </Typography>
        
        <Typography 
          variant="h6" 
          align="center" 
          color="text.secondary" 
          sx={{ mb: 6 }}
        >
          Powerful tools designed for racing enthusiasts and league organizers
        </Typography>
        
        <Grid container spacing={3}>
          {features.map((feature, index) => (
            <Grid item xs={12} sm={6} md={4} key={index}>
              <Card 
                sx={{ 
                  height: '100%',
                  transition: 'transform 0.3s, box-shadow 0.3s',
                  '&:hover': {
                    transform: 'translateY(-8px)',
                    boxShadow: theme.shadows[8],
                  },
                  background: 'linear-gradient(145deg, rgba(30,30,30,0.9), rgba(25,25,25,0.95))',
                  border: '1px solid rgba(255,255,255,0.1)',
                }}
              >
                <CardContent sx={{ p: 3 }}>
                  <Box sx={{ display: 'flex', alignItems: 'flex-start', mb: 2 }}>
                    {feature.icon}
                    <Chip 
                      label={feature.highlight} 
                      size="small" 
                      color="primary" 
                      sx={{ ml: 'auto' }}
                    />
                  </Box>
                  
                  <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
                    {feature.title}
                  </Typography>
                  
                  <Typography variant="body2" color="text.secondary">
                    {feature.description}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      </Container>

      {/* Call to Action Section */}
      <Container maxWidth="lg" sx={{ py: 8 }}>
        <Paper 
          sx={{ 
            p: 6, 
            textAlign: 'center',
            background: 'linear-gradient(135deg, #2196F3 0%, #21CBF3 100%)',
            color: 'white'
          }}
        >
          <Typography variant="h4" sx={{ mb: 2, fontWeight: 600 }}>
            Ready to Start Your Racing League?
          </Typography>
          
          <Typography variant="h6" sx={{ mb: 4, opacity: 0.9 }}>
            Join thousands of racing enthusiasts already using our platform
          </Typography>
          
          <Button 
            variant="contained" 
            size="large"
            onClick={handleGetStarted}
            sx={{ 
              bgcolor: 'white', 
              color: 'primary.main',
              py: 1.5,
              px: 4,
              '&:hover': {
                bgcolor: 'rgba(255,255,255,0.9)'
              }
            }}
            endIcon={<ArrowForwardIcon />}
          >
            {isAuthenticated ? 'Go to Dashboard' : 'Get Started Free'}
          </Button>
        </Paper>
      </Container>

      {/* Footer */}
      <Box sx={{ bgcolor: 'rgba(20,20,20,0.95)', py: 4, mt: 8 }}>
        <Container maxWidth="lg">
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <CarIcon sx={{ fontSize: 24, color: 'primary.main', mr: 1 }} />
              <Typography variant="body2" color="text.secondary">
                © 2025 Racing League Manager. All rights reserved.
              </Typography>
            </Box>
            
            <Typography variant="body2" color="text.secondary">
              Built for racing enthusiasts
            </Typography>
          </Box>
        </Container>
      </Box>
    </Box>
  );
};

export default Home;