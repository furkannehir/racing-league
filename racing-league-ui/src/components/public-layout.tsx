import React from 'react';
import { Box, Toolbar } from '@mui/material';
import PublicHeader from './public-header';

interface MainLayoutProps {
  children: React.ReactNode;
}

const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <PublicHeader />
      {/* Add an empty Toolbar as a spacer to prevent content from hiding under the AppBar */}
      <Toolbar />
      {/* Main content */}
      <Box component="main" sx={{ flexGrow: 1 }}>
        {children}
      </Box>
    </Box>
  );
};

export default MainLayout;