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
// Import other pages...

// Protected route wrapper
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();
  
  if (loading) return null;
  
  if (!isAuthenticated) {
    return <Navigate to="/login" />;
  }
  
  return <MainLayout>{children}</MainLayout>;
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
              <ProtectedRoute>
                <FindLeaguesPage />
              </ProtectedRoute>
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