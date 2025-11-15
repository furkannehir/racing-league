import React, { useState } from 'react';
import { Navigate, Link } from 'react-router-dom';
import {
  Box,
  Container,
  Paper,
  TextField,
  Button,
  Typography,
  Alert,
  CircularProgress,
  Divider,
  Tabs,
  Tab,
  InputAdornment,
  IconButton,
  Grid,
  useMediaQuery,
  useTheme,
  Card,
  CardContent
} from '@mui/material';
import {
  Google as GoogleIcon,
  Visibility,
  VisibilityOff,
  Email as EmailIcon,
  Person as PersonIcon,
  Lock as LockIcon,
  EmojiEvents as TrophyIcon,
  Group as GroupIcon,
  Timeline as TimelineIcon,
  Leaderboard as LeaderboardIcon,
  DirectionsCar as CarIcon,
  Send as SendIcon
} from '@mui/icons-material';
import { useAuth } from '../hooks/useAuth';
import { verification_email } from '../services/api';
import PublicHeader from '../components/public-header';

// Import racing background image
// You should place your image in the public folder or src/assets
const backgroundImage = 'login_background.png'; 

const Login: React.FC = () => {
  // Form state
  const [mode, setMode] = useState<'login' | 'signup'>('login');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [passwordError, setPasswordError] = useState('');
  const [message, setMessage] = useState<string | null>(null);
  const [showResendVerification, setShowResendVerification] = useState(false);
  const [resendingVerification, setResendingVerification] = useState(false);
  const [verificationEmail, setVerificationEmail] = useState('');

  // Auth context
  const { login, signup, googleLogin, isAuthenticated, loading, error } = useAuth();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  // Redirect if already authenticated
  if (isAuthenticated) {
    return <Navigate to="/" />;
  }

  const validatePassword = () => {
    if (mode === 'signup' && password !== confirmPassword) {
      setPasswordError("Passwords don't match");
      return false;
    }
    setPasswordError('');
    return true;
  };

  const handleModeChange = (newMode: 'login' | 'signup') => {
    setMode(newMode);
    setShowResendVerification(false);
    setMessage(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validatePassword()) return;
    
    setShowResendVerification(false);
    setMessage(null);
    
    try {
      if (mode === 'login') {
        await login(email, password);
        // Use window.location for a hard navigation to ensure state is updated
        window.location.href = '/dashboard';
      } else {
        await signup(name, email, password);
        setMessage('Registration successful! Please check your email to verify your account.');
        setShowResendVerification(true);
        setVerificationEmail(email);
      }
    } catch (err: any) {
      // Check if error is related to email verification
      const errorMessage = err.message || '';
      if (errorMessage.toLowerCase().includes('verify') || 
          errorMessage.toLowerCase().includes('verification') ||
          errorMessage.toLowerCase().includes('not verified')) {
        setShowResendVerification(true);
        setVerificationEmail(email);
      }
    }
  };

  const handleResendVerification = async () => {
    setResendingVerification(true);
    try {
      await verification_email(verificationEmail);
      setMessage('Verification email sent! Please check your inbox.');
    } catch (err) {
      setMessage('Verification email sent! Please check your inbox.');
    } finally {
      setResendingVerification(false);
      setShowResendVerification(false);
    }
  };

  const handleGoogleLogin = async () => {
    try {
      await googleLogin();
      window.location.href = '/dashboard';
    } catch (err) {
      // Error is handled by useAuth
    }
  };

  const features = [
    {
      icon: <TrophyIcon sx={{ fontSize: 36, color: 'gold' }} />,
      title: 'Create Racing Leagues',
      description: 'Create your own racing leagues and invite friends to compete!'
    },
    {
      icon: <LeaderboardIcon sx={{ fontSize: 36, color: '#0088ff' }} />,
      title: 'Track Standings',
      description: 'Keep track of championship standings, race results, and statistics.'
    },
    {
      icon: <TimelineIcon sx={{ fontSize: 36, color: '#00cc88' }} />,
      title: 'Manage Your Season',
      description: 'Set up race calendars, point systems, and manage events.'
    },
    {
      icon: <GroupIcon sx={{ fontSize: 36, color: '#ff6600' }} />,
      title: 'Join Communities',
      description: 'Find and join public leagues to race with other enthusiasts.'
    },
  ];

  return (
    <Box
      sx={{
        minHeight: '100vh', 
        minWidth: '100vw', 
        bgcolor: 'background.default',
        backgroundImage: `url(${backgroundImage})`,
        backgroundSize: 'cover',
        backgroundColor: 'rgba(0, 0, 0, 0.7)',
        backgroundPosition: 'center',
        backgroundRepeat: 'no-repeat',
        backgroundAttachment: 'fixed',
        
      }}
    >
      <PublicHeader />
      <Container>
        <Grid 
          container 
          spacing={3} 
          alignItems="center"
          justifyContent="center"
          sx={{ minHeight: '90vh' }}
          >
          {/* Left side: Auth form */}
          <Grid item xs={12} md={6}>
            <Box
              sx={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
              }}
            >
              <Paper
                elevation={4}
                sx={{
                  padding: 4,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  width: '100%',
                  background: 'linear-gradient(180deg, rgba(30,30,30,0.9) 0%, rgba(20,20,20,0.95) 100%)',
                  borderRadius: 2,
                  backdropFilter: 'blur(10px)',
                  boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
                }}
              >
                <Box 
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                    mb: 2
                  }}
                >
                  <CarIcon sx={{ fontSize: 32, color: 'primary.main' }} />
                  <Typography component="h1" variant="h5" sx={{ fontWeight: 'bold', color: 'primary.main' }}>
                    Racing League
                  </Typography>
                </Box>
                
                <Tabs
                  value={mode}
                  onChange={(_, newValue) => handleModeChange(newValue)}
                  sx={{ mb: 3, width: '100%' }}
                  centered
                  indicatorColor="primary"
                  textColor="primary"
                >
                  <Tab label="Sign In" value="login" />
                  <Tab label="Sign Up" value="signup" />
                </Tabs>

                {error && (
                  <Alert severity="error" sx={{ width: '100%', mb: 2 }}>
                    {error}
                  </Alert>
                )}
                {message && (
                  <Alert severity="success" sx={{ width: '100%', mb: 2 }}>
                    {message}
                  </Alert>
                )}
                {showResendVerification && (
                  <Box sx={{ width: '100%', mb: 2 }}>
                    <Button
                      fullWidth
                      variant="outlined"
                      startIcon={<SendIcon />}
                      onClick={handleResendVerification}
                      disabled={resendingVerification}
                      sx={{ textTransform: 'none' }}
                    >
                      {resendingVerification ? (
                        <CircularProgress size={24} />
                      ) : (
                        'Resend Verification Email'
                      )}
                    </Button>
                  </Box>
                )}

                <Box component="form" onSubmit={handleSubmit} sx={{ width: '100%' }}>
                  {/* Name field - only show in signup mode */}
                  {mode === 'signup' && (
                    <TextField
                      margin="normal"
                      required
                      fullWidth
                      id="name"
                      label="Full Name"
                      name="name"
                      autoComplete="name"
                      autoFocus={mode === 'signup'}
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      disabled={loading}
                      InputProps={{
                        startAdornment: (
                          <InputAdornment position="start">
                            <PersonIcon color="action" />
                          </InputAdornment>
                        ),
                      }}
                    />
                  )}
                  
                  {/* Email field - shown in both modes */}
                  <TextField
                    margin="normal"
                    required
                    fullWidth
                    id="email"
                    label="Email Address"
                    name="email"
                    autoComplete="email"
                    autoFocus={mode === 'login'}
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    disabled={loading}
                    InputProps={{
                      startAdornment: (
                        <InputAdornment position="start">
                          <EmailIcon color="action" />
                        </InputAdornment>
                      ),
                    }}
                  />
                  
                  {/* Password field */}
                  <TextField
                    margin="normal"
                    required
                    fullWidth
                    name="password"
                    label="Password"
                    type={showPassword ? "text" : "password"}
                    id="password"
                    autoComplete={mode === 'login' ? "current-password" : "new-password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    disabled={loading}
                    InputProps={{
                      startAdornment: (
                        <InputAdornment position="start">
                          <LockIcon color="action" />
                        </InputAdornment>
                      ),
                      endAdornment: (
                        <InputAdornment position="end">
                          <IconButton
                            aria-label="toggle password visibility"
                            onClick={() => setShowPassword(!showPassword)}
                            edge="end"
                          >
                            {showPassword ? <VisibilityOff /> : <Visibility />}
                          </IconButton>
                        </InputAdornment>
                      )
                    }}
                  />
                  
                  {/* Confirm Password field - only show in signup mode */}
                  {mode === 'signup' && (
                    <TextField
                      margin="normal"
                      required
                      fullWidth
                      name="confirmPassword"
                      label="Confirm Password"
                      type={showPassword ? "text" : "password"}
                      id="confirmPassword"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      disabled={loading}
                      error={!!passwordError}
                      helperText={passwordError}
                      InputProps={{
                        startAdornment: (
                          <InputAdornment position="start">
                            <LockIcon color="action" />
                          </InputAdornment>
                        )
                      }}
                    />
                  )}

                  {/* Submit button */}
                  <Button
                    type="submit"
                    fullWidth
                    variant="contained"
                    sx={{ mt: 3, mb: 2 }}
                    disabled={loading}
                  >
                    {loading ? <CircularProgress size={24} /> : 
                      mode === 'login' ? 'Sign In' : 'Create Account'}
                  </Button>

                  {/* Divider with "or" text */}
                  <Box sx={{ display: 'flex', alignItems: 'center', my: 2 }}>
                    <Divider sx={{ flexGrow: 1 }} />
                    <Typography variant="body2" color="text.secondary" sx={{ mx: 2 }}>
                      OR
                    </Typography>
                    <Divider sx={{ flexGrow: 1 }} />
                  </Box>

                  {/* Google login button */}
                  <Button
                    fullWidth
                    variant="outlined"
                    startIcon={<GoogleIcon />}
                    onClick={handleGoogleLogin}
                    disabled={true}  // Temporarily disable Google login
                    sx={{
                      borderColor: '#4285F4',
                      color: '#fff',
                      textTransform: 'none',
                      '&:hover': {
                        borderColor: '#4285F4',
                        backgroundColor: 'rgba(66, 133, 244, 0.1)',
                      },
                    }}
                  >
                    Continue with Google (Coming Soon)
                  </Button>

                  {/* Additional help text */}
                  {mode === 'login' && (
                    <Typography variant="body2" align="center" sx={{ mt: 2 }}>
                      <Link to="/reset-password" style={{ color: 'inherit' }}>
                        Forgot password?
                      </Link>
                    </Typography>
                  )}
                </Box>
              </Paper>
            </Box>
          </Grid>

          {/* Right side: Features (hidden on mobile) */}
          {!isMobile && (
            <Grid item xs={12} md={6}>
              <Box sx={{ pl: { md: 4 } }}>
                <Typography 
                  variant="h4" 
                  sx={{ 
                    mb: 4, 
                    color: 'white', 
                    fontWeight: 600,
                    textShadow: '0 2px 10px rgba(0,0,0,0.5)'
                  }}
                >
                  Join the Racing Community
                </Typography>
                
                <Grid container spacing={2}>
                  {features.map((feature, index) => (
                    <Grid item xs={12} sm={6} key={index}>
                      <Card sx={{ 
                        height: '100%', 
                        backgroundColor: 'rgba(20,20,20,0.85)',
                        backdropFilter: 'blur(10px)',
                        transition: 'transform 0.2s',
                        '&:hover': {
                          transform: 'translateY(-4px)',
                        }
                      }}>
                        <CardContent>
                          <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                            {feature.icon}
                            <Typography variant="h6" sx={{ ml: 1 }}>
                              {feature.title}
                            </Typography>
                          </Box>
                          <Typography variant="body2" color="text.secondary">
                            {feature.description}
                          </Typography>
                        </CardContent>
                      </Card>
                    </Grid>
                  ))}
                </Grid>
                
                {mode === 'signup' && (
                  <Box sx={{ mt: 4, p: 2, borderRadius: 2, bgcolor: 'rgba(0,0,0,0.5)' }}>
                    <Typography variant="body1" color="primary.light" sx={{ fontWeight: 500 }}>
                      Create your account today and start racing with friends!
                    </Typography>
                  </Box>
                )}
              </Box>
            </Grid>
          )}
        </Grid>
      </Container>
    </Box>
  );
};

export default Login;