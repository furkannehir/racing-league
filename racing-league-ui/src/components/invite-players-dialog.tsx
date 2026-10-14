import React, { useState, useEffect, useRef } from 'react';
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
import { invitePlayersToLeague, fetchSentLeagueInvites, retryInvitationEmail } from '../services/api';
import { SentLeagueInvite } from '../types/league';

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
  const [sentInvites, setSentInvites] = useState<SentLeagueInvite[]>([]);
  const [retrying, setRetrying] = useState<string | null>(null);
  const dialogVersion = useRef(0);

  useEffect(() => {
    if (!open) return;
    dialogVersion.current += 1;
    let cancelled = false;
    let refreshing = false;
    setMessage(null);
    setRetrying(null);
    setIsLoading(false);
    setSentInvites([]);
    const refresh = async () => {
      if (cancelled || refreshing) return;
      refreshing = true;
      try {
        const invites = await fetchSentLeagueInvites(leagueId);
        if (!cancelled) setSentInvites(invites);
      } catch (failure) {
        if (!cancelled) setMessage({ type: 'error', text: failure instanceof Error ? failure.message : 'Could not load invitations.' });
      } finally {
        refreshing = false;
      }
    };
    void refresh();
    const timer = window.setInterval(() => { void refresh(); }, 5000);
    return () => { cancelled = true; dialogVersion.current += 1; window.clearInterval(timer); };
  }, [open, leagueId]);

  const handleRetry = async (inviteId: string) => {
    const version = dialogVersion.current;
    setRetrying(inviteId);
    try {
      await retryInvitationEmail(inviteId);
      const invites = await fetchSentLeagueInvites(leagueId);
      if (version !== dialogVersion.current) return;
      setSentInvites(invites);
      setMessage({ type: 'success', text: 'Invitation email queued for retry.' });
    } catch (failure) {
      if (version === dialogVersion.current) setMessage({ type: 'error', text: failure instanceof Error ? failure.message : 'Could not retry the invitation email.' });
    } finally {
      if (version === dialogVersion.current) setRetrying(null);
    }
  };

  // Email validation regex
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  const handleAddEmail = () => {
    if (!email.trim()) return;
    
    // Basic email validation
    const normalized = email.trim().toLowerCase();
    if (!emailRegex.test(normalized)) {
      setError('Please enter a valid email address');
      return;
    }
    
    // Check if email is already added
    if (emails.includes(normalized)) {
      setError('This email has already been added');
      return;
    }
    
    setEmails([...emails, normalized]);
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
    
    const version = dialogVersion.current;
    setIsLoading(true);
    setMessage(null);
    setError(null);
    
    try {
      const created = await invitePlayersToLeague(leagueId, emails);
      if (version !== dialogVersion.current) return;
      setMessage({ 
        type: 'success',
        text: `${created.length} invitation${created.length > 1 ? 's' : ''} created. Email notifications are queued; players join after accepting.`
      });
      setEmails([]);
      setSentInvites(current => Array.from(new Map([...current, ...created].map(invite => [invite._id, invite])).values()));
      onInvitesSent();
      
    } catch (error) {
      if (version !== dialogVersion.current) return;
      console.error('Error sending invites:', error);
      setMessage({
        type: 'error',
        text: error instanceof Error ? error.message : 'Failed to create invitations. Please try again.'
      });
    } finally {
      if (version === dialogVersion.current) setIsLoading(false);
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
        <Divider sx={{ my: 3 }} />
        <Typography variant="subtitle2" gutterBottom>Pending invitations</Typography>
        {sentInvites.length === 0 && <Typography variant="body2">No pending invitations.</Typography>}
        {sentInvites.map(invite => (
          <Box key={invite._id} sx={{ py: 1, display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
            <Typography variant="body2" sx={{ flexGrow: 1 }}>{invite.invited_email}</Typography>
            <Chip size="small" label={invite.email_status === 'sent' ? 'Email sent' :
              invite.email_status === 'failed' ? 'Email failed' :
              invite.email_status === 'unknown' ? 'Email status unavailable' : 'Email queued'}
              color={invite.email_status === 'failed' ? 'warning' : 'default'} />
            {['failed', 'unknown'].includes(invite.email_status) && (
              <Button size="small" disabled={retrying !== null} onClick={() => handleRetry(invite._id)}>
                {retrying === invite._id ? 'Queuing...' : 'Retry email'}
              </Button>
            )}
          </Box>
        ))}
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
