import React from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import {
  Box,
  Container,
  Paper,
  Typography,
  Card,
  CardContent,
  CircularProgress,
  Divider,
  Avatar,
  Chip,
  Fade,
} from '@mui/material';
import {
  Speed as SpeedIcon,
  EmojiEvents as TrophyIcon,
  Search as SearchIcon,
  Person as PersonIcon,
  Flag as FlagIcon
} from '@mui/icons-material';
import { useAuth } from '../hooks/useAuth';

const Dashboard: React.FC = () => {
  const { isAuthenticated, user, loading } = useAuth();
  const navigate = useNavigate();

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

  const navigationActions = [
    {
      title: 'My Leagues',
      icon: <TrophyIcon fontSize="large" />,
      path: '/leagues',
      description: 'View and manage your league memberships',
      color: '#1e88e5'
    },
    {
      title: 'Find Leagues',
      icon: <SearchIcon fontSize="large" />,
      path: '/search-leagues',
      description: 'Discover and join new racing leagues',
      color: '#43a047'
    },
    {
      title: 'Profile',
      icon: <PersonIcon fontSize="large" />,
      path: '/profile',
      description: 'Manage your personal information',
      color: '#e53935'
    },
  ];

  return (
    <Box 
      sx={{ 
        backgroundColor: 'background.default',
        minHeight: '90vh',
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
            <Avatar
              sx={{
                width: 64,
                height: 64,
                bgcolor: 'primary.main',
                mr: 2,
                boxShadow: '0 4px 12px rgba(0,0,0,0.2)'
              }}
            >
              <SpeedIcon sx={{ fontSize: 36 }} />
            </Avatar>
            <Box>
              <Typography variant="h4" component="h1" sx={{ fontWeight: 600 }}>
              Championship Central
              </Typography>
              <Typography color="text.secondary" variant="subtitle1">
                Welcome back, {user?.name || 'Racer'}
              </Typography>
            </Box>
          </Box>
        </Box>

        {/* Main Content */}
        <Box sx={{ mb: 4 }}>
          <Typography variant="h5" sx={{ mb: 2 }}>
            Quick Actions
          </Typography>
          <Divider sx={{ mb: 3 }} />
          
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
            {navigationActions.map((action, index) => (
              <Fade in={true} key={action.title} style={{ transitionDelay: `${index * 100}ms` }}>
                <Card
                  sx={{
                    flex: { xs: '1 1 100%', sm: '1 1 calc(50% - 16px)', md: '1 1 calc(33.333% - 16px)' },
                    cursor: 'pointer',
                    height: 180,
                    backgroundImage: `linear-gradient(135deg, rgba(40,40,40,0.8) 0%, rgba(20,20,20,0.9) 100%)`,
                    borderLeft: `4px solid ${action.color}`,
                    transition: 'all 0.3s ease',
                    '&:hover': { 
                      transform: 'translateY(-8px)',
                      boxShadow: `0 12px 20px rgba(0,0,0,0.3), 0 0 10px ${action.color}40`,
                    },
                  }}
                  onClick={() => navigate(action.path)}
                >
                  <CardContent sx={{ height: '100%', position: 'relative', p: 3 }}>
                    <Box 
                      sx={{ 
                        position: 'absolute', 
                        top: 16, 
                        right: 16,
                        backgroundColor: `${action.color}30`,
                        width: 50,
                        height: 50,
                        borderRadius: '50%',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: action.color
                      }}
                    >
                      {action.icon}
                    </Box>
                    <Box sx={{ pt: 5 }}>
                      <Typography variant="h6" gutterBottom sx={{ fontWeight: 'bold' }}>
                        {action.title}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {action.description}
                      </Typography>
                    </Box>
                  </CardContent>
                </Card>
              </Fade>
            ))}
          </Box>
        </Box>

        <Box>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h5">Dashboard Overview</Typography>
            <Chip icon={<FlagIcon />} label="Race Season: 2025" color="primary" variant="outlined" />
          </Box>
          <Divider sx={{ mb: 3 }} />
          
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
            {/* League Standings */}
            <Paper 
              sx={{ 
                flex: { xs: '1 1 100%', md: '1 1 calc(50% - 12px)' },
                p: 3,
                backgroundImage: 'linear-gradient(180deg, rgba(30,30,30,0.7) 0%, rgba(20,20,20,0.9) 100%)',
                boxShadow: '0 8px 16px rgba(0,0,0,0.2)',
                borderRadius: 2,
              }}
            >
              <Typography variant="h6" gutterBottom sx={{ 
                display: 'flex',
                alignItems: 'center',
                fontWeight: 500,
                mb: 2
              }}>
                <TrophyIcon sx={{ mr: 1, color: 'gold' }} />
                League Standings
              </Typography>
              <Divider sx={{ mb: 2 }} />
              <Box sx={{ display: 'flex', justifyContent: 'center', p: 2, height: 200 }}>
                <Typography color="text.secondary" sx={{ fontStyle: 'italic' }}>
                  Your league standings will appear here
                </Typography>
              </Box>
            </Paper>

            {/* Upcoming Races */}
            <Paper 
              sx={{ 
                flex: { xs: '1 1 100%', md: '1 1 calc(50% - 12px)' },
                p: 3,
                backgroundImage: 'linear-gradient(180deg, rgba(30,30,30,0.7) 0%, rgba(20,20,20,0.9) 100%)',
                boxShadow: '0 8px 16px rgba(0,0,0,0.2)',
                borderRadius: 2,
              }}
            >
              <Typography variant="h6" gutterBottom sx={{ 
                display: 'flex',
                alignItems: 'center',
                fontWeight: 500,
                mb: 2
              }}>
                <FlagIcon sx={{ mr: 1, color: '#f44336' }} />
                Upcoming Races
              </Typography>
              <Divider sx={{ mb: 2 }} />
              <Box sx={{ display: 'flex', justifyContent: 'center', p: 2, height: 200 }}>
                <Typography color="text.secondary" sx={{ fontStyle: 'italic' }}>
                  Your upcoming races will appear here
                </Typography>
              </Box>
            </Paper>
          </Box>
        </Box>
      </Container>
    </Box>
  );
};

export default Dashboard;