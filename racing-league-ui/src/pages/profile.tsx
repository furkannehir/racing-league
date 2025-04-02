import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Container,
  Paper,
  Typography,
  Avatar,
  Divider,
  Button,
  CircularProgress,
  Alert,
  Tabs,
  Tab,
  TextField,
  Grid,
  IconButton,
} from '@mui/material';
import {
  Person as PersonIcon,
  ArrowBack as ArrowBackIcon,
  Lock as LockIcon,
  Save as SaveIcon,
} from '@mui/icons-material';
import { fetchUserProfile, updateUserProfile, updateUserPassword, isAuthenticated } from '../services/api';
import { UserProfile } from '../types/user';

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
      id={`profile-tabpanel-${index}`}
      aria-labelledby={`profile-tab-${index}`}
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

const ProfilePage: React.FC = () => {
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState(0);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    bio: '',
  });
  const [passwordData, setPasswordData] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
  });
  const [message, setMessage] = useState({ type: '', text: '' });

  useEffect(() => {
    const checkAuthAndLoadProfile = async () => {
      // Check if user is authenticated
      if (!isAuthenticated()) {
        // Redirect to login page if not authenticated
        navigate('/login', { 
          state: { 
            from: '/profile', 
            message: 'Please log in to view your profile' 
          } 
        });
        return;
      }

      // Proceed with loading profile data
      try {
        const data = await fetchUserProfile();
        setProfile(data);
        setFormData({
          name: data.name || '',
          email: data.email || '',
          bio: data.bio || '',
        });
        setIsLoading(false);
      } catch (error) {
        setMessage({
          type: 'error',
          text: 'Failed to load profile. Please try again.',
        });
        setIsLoading(false);
      }
    };

    checkAuthAndLoadProfile();
  }, [navigate]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handlePasswordChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setPasswordData((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleTabChange = (_: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  };

  const handleProfileSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setMessage({ type: '', text: '' });
    
    try {
      setIsLoading(true);
      await updateUserProfile(formData);
      setMessage({
        type: 'success',
        text: 'Profile updated successfully!',
      });
    } catch (error) {
      setMessage({
        type: 'error',
        text: 'Failed to update profile. Please try again.',
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handlePasswordSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setMessage({ type: '', text: '' });

    // Validate passwords match
    if (passwordData.newPassword !== passwordData.confirmPassword) {
      setMessage({
        type: 'error',
        text: 'New passwords do not match.',
      });
      return;
    }
    
    try {
      setIsLoading(true);
      await updateUserPassword(passwordData);
      setPasswordData({
        currentPassword: '',
        newPassword: '',
        confirmPassword: '',
      });
      setMessage({
        type: 'success',
        text: 'Password updated successfully!',
      });
    } catch (error) {
      setMessage({
        type: 'error',
        text: 'Failed to update password. Please ensure your current password is correct.',
      });
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading && !profile) {
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
        {/* Profile header */}
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
              <PersonIcon sx={{ fontSize: 36 }} />
            </Avatar>
            <Box>
              <Typography variant="h4" component="h1" sx={{ fontWeight: 600 }}>
                User Profile
              </Typography>
              <Typography color="text.secondary" variant="subtitle1">
                Manage your personal information and password
              </Typography>
            </Box>
          </Box>
        </Box>
        
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
        
        {/* Profile content */}
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
              aria-label="profile tabs"
              indicatorColor="primary"
              textColor="primary"
              variant="scrollable"
              scrollButtons="auto"
            >
              <Tab label="Personal Information" icon={<PersonIcon />} iconPosition="start" />
              <Tab label="Password" icon={<LockIcon />} iconPosition="start" />
            </Tabs>
          </Box>
          
          {/* Personal Information Tab */}
          <TabPanel value={activeTab} index={0}>
            <Box sx={{ p: 3 }}>
              <form onSubmit={handleProfileSubmit}>
                <Grid container spacing={3}>
                  <Grid item xs={12} md={6}>
                    <TextField
                      fullWidth
                      label="Name"
                      name="name"
                      value={formData.name}
                      onChange={handleInputChange}
                      variant="outlined"
                      required
                      margin="normal"
                    />
                    
                    <TextField
                      fullWidth
                      label="Email"
                      name="email"
                      type="email"
                      value={formData.email}
                      onChange={handleInputChange}
                      variant="outlined"
                      required
                      margin="normal"
                    />
                  </Grid>
                  
                  <Grid item xs={12} md={6}>
                    <TextField
                      fullWidth
                      label="Bio"
                      name="bio"
                      value={formData.bio}
                      onChange={handleInputChange}
                      variant="outlined"
                      margin="normal"
                      multiline
                      rows={4}
                      placeholder="Tell us about yourself..."
                    />
                  </Grid>
                  
                  <Grid item xs={12} display="flex" justifyContent="flex-end">
                    <Button 
                      type="submit" 
                      variant="contained" 
                      color="primary" 
                      disabled={isLoading}
                      startIcon={<SaveIcon />}
                    >
                      {isLoading ? 'Saving...' : 'Save Changes'}
                    </Button>
                  </Grid>
                </Grid>
              </form>
            </Box>
          </TabPanel>
          
          {/* Password Tab */}
          <TabPanel value={activeTab} index={1}>
            <Box sx={{ p: 3 }}>
              <form onSubmit={handlePasswordSubmit}>
                <Grid container spacing={3}>
                  <Grid item xs={12} md={6}>
                    <Typography variant="h6" gutterBottom>Change Password</Typography>
                    <Divider sx={{ mb: 2 }} />
                    
                    <TextField
                      fullWidth
                      label="Current Password"
                      name="currentPassword"
                      type="password"
                      value={passwordData.currentPassword}
                      onChange={handlePasswordChange}
                      variant="outlined"
                      required
                      margin="normal"
                    />
                    
                    <TextField
                      fullWidth
                      label="New Password"
                      name="newPassword"
                      type="password"
                      value={passwordData.newPassword}
                      onChange={handlePasswordChange}
                      variant="outlined"
                      required
                      margin="normal"
                    />
                    
                    <TextField
                      fullWidth
                      label="Confirm New Password"
                      name="confirmPassword"
                      type="password"
                      value={passwordData.confirmPassword}
                      onChange={handlePasswordChange}
                      variant="outlined"
                      required
                      margin="normal"
                    />
                    
                    <Box mt={2} display="flex" justifyContent="flex-end">
                      <Button 
                        type="submit" 
                        variant="contained" 
                        color="primary" 
                        disabled={isLoading}
                        startIcon={<LockIcon />}
                      >
                        {isLoading ? 'Updating...' : 'Update Password'}
                      </Button>
                    </Box>
                  </Grid>
                  
                  <Grid item xs={12} md={6}>
                    <Paper sx={{ p: 3, bgcolor: 'rgba(0,0,0,0.2)' }}>
                      <Typography variant="h6" gutterBottom>Password Requirements</Typography>
                      <Typography variant="body2" paragraph>
                        For your security, please ensure your password:
                      </Typography>
                      <ul>
                        <Typography component="li" variant="body2">
                          Is at least 8 characters long
                        </Typography>
                        <Typography component="li" variant="body2">
                          Contains at least one uppercase letter
                        </Typography>
                        <Typography component="li" variant="body2">
                          Contains at least one lowercase letter
                        </Typography>
                        <Typography component="li" variant="body2">
                          Contains at least one number
                        </Typography>
                        <Typography component="li" variant="body2">
                          Contains at least one special character
                        </Typography>
                      </ul>
                    </Paper>
                  </Grid>
                </Grid>
              </form>
            </Box>
          </TabPanel>
        </Paper>
      </Container>
    </Box>
  );
};

export default ProfilePage;