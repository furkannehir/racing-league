import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Box,
  Container,
  Paper,
  TextField,
  Button,
  Typography,
  Alert,
  CircularProgress,
  InputAdornment,
} from '@mui/material';
import {
  Email as EmailIcon,
  ArrowBack as ArrowBackIcon,
  DirectionsCar as CarIcon,
} from '@mui/icons-material';
import { reset_password } from '../services/api';
import PublicHeader from '../components/public-header';

const backgroundImage = 'login_background.png';

const ResetPassword: React.FC = () => {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessMessage(null);
    setLoading(true);

    try {
      await reset_password(email);
      setSuccessMessage('If the email is real reset link is sent to your email');
      setEmail(''); // Clear the email field
    } catch (err) {
      // Don't show specific errors to prevent user enumeration
      setSuccessMessage('If the email is real reset link is sent to your email');
      setEmail(''); // Clear the email field even on error
    } finally {
      setLoading(false);
    }
  };

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
      <Container 
        maxWidth="sm"
        sx={{
          display: 'flex',
          justifyContent: 'center',
            alignItems: 'center',
            minHeight: '80vh',
        }}
    >
        <Paper
          elevation={4}
          sx={{
            padding: 4,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
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
              mb: 2,
            }}
          >
            <CarIcon sx={{ fontSize: 32, color: 'primary.main' }} />
            <Typography component="h1" variant="h5" sx={{ fontWeight: 'bold', color: 'primary.main' }}>
              Racing League
            </Typography>
          </Box>

          <Typography component="h2" variant="h6" sx={{ mb: 1 }}>
            Forgot Password
          </Typography>

          <Typography variant="body2" color="text.secondary" sx={{ mb: 3, textAlign: 'center' }}>
            Enter your email address and we'll send you a link to reset your password.
          </Typography>

          {error && (
            <Alert severity="error" sx={{ width: '100%', mb: 2 }}>
              {error}
            </Alert>
          )}

          {successMessage && (
            <Alert severity="success" sx={{ width: '100%', mb: 2 }}>
              {successMessage}
            </Alert>
          )}

          <Box component="form" onSubmit={handleSubmit} sx={{ width: '100%' }}>
            <TextField
              margin="normal"
              required
              fullWidth
              id="email"
              label="Email Address"
              name="email"
              autoComplete="email"
              autoFocus
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

            <Button
              type="submit"
              fullWidth
              variant="contained"
              sx={{ mt: 3, mb: 2 }}
              disabled={loading}
            >
              {loading ? <CircularProgress size={24} /> : 'Send Reset Link'}
            </Button>

            <Box sx={{ display: 'flex', justifyContent: 'center', mt: 2 }}>
              <Link to="/login" style={{ textDecoration: 'none' }}>
                <Button
                  startIcon={<ArrowBackIcon />}
                  sx={{
                    color: 'text.secondary',
                    textTransform: 'none',
                    '&:hover': {
                      color: 'primary.main',
                    },
                  }}
                >
                  Back to Login
                </Button>
              </Link>
            </Box>
          </Box>
        </Paper>
      </Container>
    </Box>
  );
};

export default ResetPassword;
