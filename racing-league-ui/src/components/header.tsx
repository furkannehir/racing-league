import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import {
  AppBar,
  Toolbar,
  Typography,
  Box,
  IconButton,
  Button,
  Avatar,
  Menu,
  MenuItem,
  ListItemIcon,
  Divider,
  useTheme,
  useMediaQuery
} from '@mui/material';
import {
  Menu as MenuIcon,
  Logout as LogoutIcon,
  AccountCircle as ProfileIcon,
  Settings as SettingsIcon,
  EmojiEvents as TrophyIcon,
  Dashboard as DashboardIcon,
  Search as SearchIcon
} from '@mui/icons-material';
import { useAuth } from '../hooks/useAuth';

const AppHeader: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  
  // User menu state
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const open = Boolean(anchorEl);
  
  // Mobile navigation menu state
  const [mobileMenuAnchor, setMobileMenuAnchor] = useState<null | HTMLElement>(null);
  const mobileMenuOpen = Boolean(mobileMenuAnchor);

  const handleProfileMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };
  
  const handleMobileMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setMobileMenuAnchor(event.currentTarget);
  };

  const handleMobileMenuClose = () => {
    setMobileMenuAnchor(null);
  };

  const handleLogout = () => {
    handleMenuClose();
    logout();
    navigate('/login');
  };

  return (
    <AppBar position="fixed" sx={{ zIndex: theme.zIndex.drawer + 1 }}>
      <Toolbar>
        {/* Logo/Brand */}
        <Box 
          component={Link} 
          to="/" 
          sx={{ 
            display: 'flex', 
            alignItems: 'center', 
            textDecoration: 'none', 
            color: 'inherit',
            flexGrow: 0
          }}
        >
          <TrophyIcon sx={{ mr: 1 }} />
          <Typography variant="h6" noWrap component="div" sx={{ fontWeight: 600 }}>
            Racing League
          </Typography>
        </Box>

        {/* Navigation for desktop */}
        {!isMobile && (
          <Box sx={{ display: 'flex', mx: 4 }}>
            <Button 
              color="inherit" 
              startIcon={<DashboardIcon />}
              onClick={() => navigate('/dashboard')}
            >
              Dashboard
            </Button>
            <Button 
              color="inherit" 
              startIcon={<TrophyIcon />}
              onClick={() => navigate('/leagues')}
            >
              My Leagues
            </Button>
            <Button 
              color="inherit" 
              startIcon={<SearchIcon />}
              onClick={() => navigate('/search-leagues')}
            >
              Find Leagues
            </Button>
          </Box>
        )}

        {/* Spacer */}
        <Box sx={{ flexGrow: 1 }} />

        {/* User Section */}
        {user ? (
          <>
            {/* Mobile menu button */}
            {isMobile && (
              <IconButton
                color="inherit"
                onClick={handleMobileMenuOpen}
                sx={{ mr: 2 }}
              >
                <MenuIcon />
              </IconButton>
            )}
            
            {/* User profile button */}
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <Typography variant="body1" sx={{ mr: 1, display: { xs: 'none', sm: 'block' } }}>
                {user.name}
              </Typography>
              <IconButton
                onClick={handleProfileMenuOpen}
                size="small"
                aria-controls={open ? 'account-menu' : undefined}
                aria-haspopup="true"
                aria-expanded={open ? 'true' : undefined}
              >
                <Avatar sx={{ width: 32, height: 32, bgcolor: 'primary.dark' }}>
                  {user.name?.charAt(0)?.toUpperCase() || 'U'}
                </Avatar>
              </IconButton>
            </Box>
          </>
        ) : (
          <>
            <Button color="inherit" onClick={() => navigate('/login')}>
              Login
            </Button>
            <Button variant="contained" onClick={() => navigate('/register')} sx={{ ml: 1 }}>
              Register
            </Button>
          </>
        )}
      </Toolbar>

      {/* User profile menu */}
      <Menu
        anchorEl={anchorEl}
        id="account-menu"
        open={open}
        onClose={handleMenuClose}
        PaperProps={{
          sx: {
            mt: 1.5,
            minWidth: 200,
          }
        }}
        transformOrigin={{ horizontal: 'right', vertical: 'top' }}
        anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
      >
        <MenuItem onClick={() => { handleMenuClose(); navigate('/profile'); }}>
          <ListItemIcon>
            <ProfileIcon fontSize="small" />
          </ListItemIcon>
          My Profile
        </MenuItem>
        <MenuItem onClick={() => { handleMenuClose(); navigate('/settings'); }}>
          <ListItemIcon>
            <SettingsIcon fontSize="small" />
          </ListItemIcon>
          Settings
        </MenuItem>
        <Divider />
        <MenuItem onClick={handleLogout}>
          <ListItemIcon>
            <LogoutIcon fontSize="small" color="error" />
          </ListItemIcon>
          Logout
        </MenuItem>
      </Menu>

      {/* Mobile navigation menu */}
      <Menu
        anchorEl={mobileMenuAnchor}
        id="mobile-menu"
        open={mobileMenuOpen}
        onClose={handleMobileMenuClose}
        PaperProps={{
          sx: {
            mt: 1.5,
            width: '200px',
          }
        }}
        transformOrigin={{ horizontal: 'right', vertical: 'top' }}
        anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
      >
        <MenuItem onClick={() => { handleMobileMenuClose(); navigate('/dashboard'); }}>
          <ListItemIcon>
            <DashboardIcon fontSize="small" />
          </ListItemIcon>
          Dashboard
        </MenuItem>
        <MenuItem onClick={() => { handleMobileMenuClose(); navigate('/leagues'); }}>
          <ListItemIcon>
            <TrophyIcon fontSize="small" />
          </ListItemIcon>
          My Leagues
        </MenuItem>
        <MenuItem onClick={() => { handleMobileMenuClose(); navigate('/search-leagues'); }}>
          <ListItemIcon>
            <SearchIcon fontSize="small" />
          </ListItemIcon>
          Find Leagues
        </MenuItem>
      </Menu>
    </AppBar>
  );
};

export default AppHeader;