import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { AuthProvider, useAuth } from './hooks/useAuth';
import theme from './theme';

// Components
import MainLayout from './components/main-layout';

// Pages
import Login from './pages/login';
import MyLeagues from './pages/my-leagues';
import LeagueDetails from './pages/league-details';
import Dashboard from './pages/dashboard';
import CreateLeague from './pages/create-league';
import ProfilePage from './pages/profile';
import FindLeaguesPage from './pages/filnd-leagues';
import Home from './pages/home';
import PublicLayout from './components/public-layout';
import ResetPassword from './pages/reset-password';
// Import other pages...

// Protected route wrapper
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();
  
  if (loading) return null;
  
  if (!isAuthenticated) {
    return <Navigate to="/" />;
  }
  
  return <MainLayout>{children}</MainLayout>;
};

// Conditional layout wrapper for public pages
const ConditionalLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();
  
  if (loading) return null;
  
  if (isAuthenticated) {
    return <MainLayout>{children}</MainLayout>;
  }
  else {
    // If not authenticated, render children without layout
    return <PublicLayout>{children}</PublicLayout>;
  }
};

const App: React.FC = () => {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            {/* Public routes */}
            <Route path="/login" element={<Login />} />
            
            {/* Protected routes with layout */}
            <Route path="/" element={
                <Home />
            } />
            <Route path="/reset-password" element={
              <ResetPassword />
            } />
            <Route path="/dashboard" element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            } />
            <Route path="/leagues" element={
              <ProtectedRoute>
                <MyLeagues />
              </ProtectedRoute>
            } />
            <Route path="/leagues/:leagueId" element={
              <ProtectedRoute>
                <LeagueDetails />
              </ProtectedRoute>
            } />
            <Route path="/create-league" element={
              <ProtectedRoute>
                <CreateLeague />
              </ProtectedRoute>
            } />
            <Route path="/profile" element={
              <ProtectedRoute>
                <ProfilePage />
              </ProtectedRoute>
            } />
            <Route path="/search-leagues" element={
              <ConditionalLayout>
                <FindLeaguesPage />
              </ConditionalLayout>
            } />

            {/* Add other protected routes */}
            
            {/* Fallback route */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
};

export default App;