import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  Box,
  Typography,
  CircularProgress,
  Chip,
  Alert,
  Divider,
  IconButton,
} from '@mui/material';
import {
  Add as AddIcon,
  Close as CloseIcon,
  Email as EmailIcon,
  Send as SendIcon,
} from '@mui/icons-material';
import { invitePlayersToLeague } from '../services/api';

interface InvitePlayersDialogProps {
  open: boolean;
  leagueId: string;
  leagueName: string;
  onClose: () => void;
  onInvitesSent: () => void;
}

const InvitePlayersDialog: React.FC<InvitePlayersDialogProps> = ({
  open,
  leagueId,
  leagueName,
  onClose,
  onInvitesSent,
}) => {
  const [email, setEmail] = useState('');
  const [emails, setEmails] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Email validation regex
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  const handleAddEmail = () => {
    if (!email.trim()) return;
    
    // Basic email validation
    if (!emailRegex.test(email)) {
      setError('Please enter a valid email address');
      return;
    }
    
    // Check if email is already added
    if (emails.includes(email)) {
      setError('This email has already been added');
      return;
    }
    
    setEmails([...emails, email]);
    setEmail('');
    setError(null);
  };

  const handleRemoveEmail = (emailToRemove: string) => {
    setEmails(emails.filter(e => e !== emailToRemove));
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleAddEmail();
    }
  };

  const handleSendInvites = async () => {
    if (emails.length === 0) {
      setError('Please add at least one email');
      return;
    }
    
    setIsLoading(true);
    setMessage(null);
    setError(null);
    
    try {
      await invitePlayersToLeague(leagueId, emails);
      setMessage({ 
        type: 'success',
        text: `Successfully sent ${emails.length} invitation${emails.length > 1 ? 's' : ''}!`
      });
      setEmails([]);
      
      // Notify parent component that invites were sent
      setTimeout(() => {
        onInvitesSent();
      }, 2000);
      
    } catch (error) {
      console.error('Error sending invites:', error);
      setMessage({
        type: 'error',
        text: 'Failed to send invitations. Please try again.'
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleClose = () => {
    setEmail('');
    setEmails([]);
    setMessage(null);
    setError(null);
    onClose();
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      fullWidth
      maxWidth="sm"
      PaperProps={{
        sx: {
          bgcolor: 'rgba(30,30,30,0.95)',
          backgroundImage: 'linear-gradient(180deg, rgba(30,30,30,0.9) 0%, rgba(25,25,25,1) 100%)',
          boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
        }
      }}
    >
      <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <EmailIcon sx={{ mr: 1 }} />
          Invite Players to {leagueName}
        </Box>
        <IconButton onClick={handleClose} size="small">
          <CloseIcon />
        </IconButton>
      </DialogTitle>
      
      <DialogContent>
        {message && (
          <Alert 
            severity={message.type} 
            sx={{ mb: 3 }}
            onClose={() => setMessage(null)}
          >
            {message.text}
          </Alert>
        )}
        
        <Typography variant="body2" sx={{ mb: 2 }}>
          Enter email addresses to invite players to join this league.
        </Typography>
        
        <Box sx={{ display: 'flex', gap: 1, mb: 1 }}>
          <TextField
            fullWidth
            label="Email Address"
            value={email}
            onChange={(e) => {
              setEmail(e.target.value);
              setError(null);
            }}
            onKeyPress={handleKeyPress}
            error={!!error}
            helperText={error}
            disabled={isLoading}
            placeholder="player@example.com"
          />
          <Button
            onClick={handleAddEmail}
            variant="contained"
            color="primary"
            disabled={!email.trim() || isLoading}
            startIcon={<AddIcon />}
          >
            Add
          </Button>
        </Box>
        
        {emails.length > 0 && (
          <>
            <Box sx={{ mt: 3, mb: 2 }}>
              <Typography variant="subtitle2" gutterBottom>
                Players to invite ({emails.length}):
              </Typography>
              <Box 
                sx={{ 
                  display: 'flex', 
                  flexWrap: 'wrap', 
                  gap: 1, 
                  p: 2,
                  borderRadius: 1,
                  bgcolor: 'rgba(0,0,0,0.2)',
                  minHeight: '100px'
                }}
              >
                {emails.map((email) => (
                  <Chip
                    key={email}
                    label={email}
                    onDelete={() => handleRemoveEmail(email)}
                    color="primary"
                    variant="outlined"
                    size="medium"
                    sx={{ mb: 1 }}
                  />
                ))}
              </Box>
            </Box>
            
            <Divider sx={{ my: 2 }} />
            
            <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
              <Button
                onClick={handleSendInvites}
                variant="contained"
                color="primary"
                disabled={isLoading}
                startIcon={isLoading ? <CircularProgress size={20} /> : <SendIcon />}
              >
                {isLoading ? 'Sending...' : `Send ${emails.length} Invitation${emails.length > 1 ? 's' : ''}`}
              </Button>
            </Box>
          </>
        )}
      </DialogContent>
      
      <DialogActions sx={{ p: 2, pt: 0 }}>
        <Button onClick={handleClose} disabled={isLoading}>
          Close
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default InvitePlayersDialog;