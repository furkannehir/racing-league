import { useNavigate } from 'react-router-dom';
import {
  AppBar,
  Toolbar,
  Typography,
  Box,
  Button
} from '@mui/material';
import LoginIcon from '@mui/icons-material/Login';
import SignUpIcon from '@mui/icons-material/HowToReg';
import { useAuth } from '../hooks/useAuth';


const PublicHeader = () => {
    
        const { isAuthenticated } = useAuth();
        const navigate = useNavigate();

    return (
        <AppBar 
        position="static" 
        sx={{ 
          bgcolor: 'transparent',
          boxShadow: 'none',
          borderBottom: '1px solid rgba(255,255,255,0.1)'
        }}
      >
        <Toolbar>
          <Box
            component="div"
            onClick={() => navigate('/')}
            sx={{ 
              display: 'flex', 
              alignItems: 'center', 
              cursor: 'pointer', 
              textDecoration: 'none', 
              color: 'inherit',
              flexGrow: 1
            }}>
            <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
              Push To Pass
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
    )
}

export default PublicHeader;