import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Container,
  Paper,
  Typography,
  TextField,
  Button,
  FormControl,
  FormControlLabel,
  FormHelperText,
  Switch,
  Divider,
  Grid,
  Stepper,
  Step,
  StepLabel,
  Alert,
  CircularProgress,
  Chip,
  IconButton,
  TableContainer,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  InputLabel,
  Select,
  MenuItem,
} from '@mui/material';
import {
  ArrowBack as ArrowBackIcon,
  Help as HelpIcon,
  Add as AddIcon,
  Delete as DeleteIcon,
  Check as CheckIcon,
} from '@mui/icons-material';
import { createLeague } from '../services/api';
import { useAuth } from '../hooks/useAuth';

interface FormValues {
    name: string;
    max_players: number;
    fastestLapPoint: number;
    public: boolean;
    pointSystem: Record<string, number>;
    calendar: Array<{track: string, date: string}>;
    invites: string[]; // Change from participants to invites
    creatorParticipates: boolean; // New field to track if creator joins their own league
  }
  
  // Updated defaultPointSystem to be an object
  const defaultPointSystem: Record<string, number> = {
    "1": 25,
    "2": 18,
    "3": 15,
    "4": 12,
    "5": 10,
    "6": 8,
    "7": 6,
    "8": 4,
    "9": 2,
    "10": 1
  };

const CreateLeague: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [activeStep, setActiveStep] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [trackInput, setTrackInput] = useState('');
  const [dateInput, setDateInput] = useState('');
  const [inviteEmail, setInviteEmail] = useState('');
  const [errors, setErrors] = useState({
    name: '',
    max_players: '',
    fastestLapPoint: '',
    pointSystem: '',
    calendar: '',
    invites: '' // Changed from participants
  });
  
  // Form state
  const [formValues, setFormValues] = useState<FormValues>({
    name: '',
    max_players: 20,
    fastestLapPoint: 1,
    public: true,
    pointSystem: {...defaultPointSystem},
    calendar: [],
    invites: [], // Changed from participants
    creatorParticipates: true // Default to true - creator joins their league
  });
  
  // Steps for the stepper
  const steps = ['League Details', 'Calendar', 'Scoring System', 'Invite Players', 'Review & Create'];

  const validateStep = (step: number): boolean => {
    const newErrors = { ...errors };
    let isValid = true;
    
    if (step === 0) {
      // Validate league details
      if (!formValues.name.trim()) {
        newErrors.name = 'League name is required';
        isValid = false;
      } else if (formValues.name.length < 3) {
        newErrors.name = 'League name must be at least 3 characters';
        isValid = false;
      } else {
        newErrors.name = '';
      }
      
      if (formValues.max_players < 2) {
        newErrors.max_players = 'League must allow at least 2 players';
        isValid = false;
      } else if (formValues.max_players > 100) {
        newErrors.max_players = 'Maximum 100 players allowed';
        isValid = false;
      } else {
        newErrors.max_players = '';
      }
    }
    
    if (step === 1) {
      // Validate calendar (optional, can proceed without races)
      newErrors.calendar = '';
    }
    
    if (step === 2) {
      // Validate scoring system
      if (formValues.fastestLapPoint < 0) {
        newErrors.fastestLapPoint = 'Fastest lap points cannot be negative';
        isValid = false;
      } else {
        newErrors.fastestLapPoint = '';
      }
      
      if (formValues.pointSystem.length === 0) {
        newErrors.pointSystem = 'At least one position must earn points';
        isValid = false;
      } else {
        newErrors.pointSystem = '';
      }
    }
    
    setErrors(newErrors);
    return isValid;
  };
  
  const addRace = () => {
    if (!trackInput.trim() || !dateInput) return;
    
    const formattedDate = new Date(dateInput).toISOString();
    
    setFormValues({
      ...formValues,
      calendar: [
        ...formValues.calendar, 
        { track: trackInput.trim(), date: formattedDate }
      ]
    });
    
    // Clear inputs
    setTrackInput('');
    setDateInput('');
  };
  
  // Remove race from calendar
  const removeRace = (index: number) => {
    const newCalendar = [...formValues.calendar];
    newCalendar.splice(index, 1);
    setFormValues({
      ...formValues,
      calendar: newCalendar
    });
  };
  
  const addInvite = () => {
    if (!inviteEmail.trim() || !inviteEmail.includes('@')) return;
    
    if (!formValues.invites.includes(inviteEmail)) {
      setFormValues({
        ...formValues,
        invites: [...formValues.invites, inviteEmail.trim()]
      });
    }
    
    setInviteEmail('');
  };
  
  const removeInvite = (email: string) => {
    setFormValues({
      ...formValues,
      invites: formValues.invites.filter(p => p !== email)
    });
  };
  
  // Update functions for handling point system changes
  const updatePointValue = (position: string, value: number) => {
    setFormValues({
      ...formValues,
      pointSystem: {
        ...formValues.pointSystem,
        [position]: value
      }
    });
  };
  
  const addPointPosition = () => {
    const nextPosition = (Object.keys(formValues.pointSystem).length + 1).toString();
    setFormValues({
      ...formValues,
      pointSystem: {
        ...formValues.pointSystem,
        [nextPosition]: 0
      }
    });
  };
  
  const removePointPosition = (position: string) => {
    const newPointSystem = { ...formValues.pointSystem };
    delete newPointSystem[position];
    
    // Renumber positions
    const sortedPositions = Object.keys(newPointSystem)
      .sort((a, b) => parseInt(a) - parseInt(b));
    
    const renumberedSystem: Record<string, number> = {};
    sortedPositions.forEach((_, idx) => {
      const pos = (idx + 1).toString();
      renumberedSystem[pos] = newPointSystem[sortedPositions[idx]];
    });
    
    setFormValues({
      ...formValues,
      pointSystem: renumberedSystem
    });
  };
  
  // Update handleSubmit to include the owner and admin
  const handleSubmit = async () => {
    if (!validateStep(activeStep)) return;
    
    try {
      setIsLoading(true);
      setError(null);
      
      // Get user email from auth
      const userEmail = user?.email;
      
      if (!userEmail) {
        setError("User email not found. Please ensure you are logged in.");
        setIsLoading(false);
        return;
      }
      
      // Determine next race
      const sortedCalendar = [...formValues.calendar]
        .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
      
      const next_race = sortedCalendar.length > 0 ? sortedCalendar[0] : null;
      
      // Initialize participants array based on whether creator participates
      const initialParticipants = formValues.creatorParticipates ? [userEmail] : [];
      
      // Create league API call with updated structure
      const createdLeague = await createLeague({
        name: formValues.name,
        owner: userEmail,
        public: formValues.public,
        calendar: formValues.calendar || [],
        pointSystem: formValues.pointSystem,
        max_players: formValues.max_players,
        fastestLapPoint: formValues.fastestLapPoint,
        participants: initialParticipants, 
        participantsCount: initialParticipants.length,
        invites: formValues.invites, 
        next_race,
        status: "active",
        admins: [userEmail],
      });
      
      setSuccess(true);
      
      // Redirect to the new league page after a short delay
      setTimeout(() => {
        navigate(`/leagues/${createdLeague._id}`);
      }, 1500);
      
    } catch (err: any) {
      setError(err?.response?.data?.message || 'Failed to create league. Please try again.');
      console.error('Error creating league:', err);
    } finally {
      setIsLoading(false);
    }
  };
  
  const handleNext = () => {
    if (validateStep(activeStep)) {
      setActiveStep((prevStep) => prevStep + 1);
    }
  };
  
  const handleBack = () => {
    setActiveStep((prevStep) => prevStep - 1);
  };
  
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    
    // For number inputs, convert string to number
    if (name === 'max_players' || name === 'fastestLapPoint') {
      setFormValues({
        ...formValues,
        [name]: parseInt(value, 10) || 0,
      });
    } else {
      setFormValues({
        ...formValues,
        [name]: value,
      });
    }
  };
  
  const handleSwitchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormValues({
      ...formValues,
      [e.target.name]: e.target.checked,
    });
  };
  
  
  const renderStepContent = (step: number) => {
    switch (step) {
      case 0:
        return (
          <Grid container spacing={3}>
            <Grid item xs={12}>
              <TextField
                name="name"
                label="League Name"
                fullWidth
                value={formValues.name}
                onChange={handleInputChange}
                error={Boolean(errors.name)}
                helperText={errors.name}
                placeholder="Ex: F1 2023 Championship"
                required
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <TextField
                name="max_players"
                label="Maximum Players"
                type="number"
                fullWidth
                value={formValues.max_players}
                onChange={handleInputChange}
                error={Boolean(errors.max_players)}
                helperText={errors.max_players || 'Maximum number of drivers allowed in your league'}
                inputProps={{ min: 2, max: 100 }}
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <FormControl fullWidth>
                <FormControlLabel
                  control={
                    <Switch
                      checked={formValues.public}
                      onChange={handleSwitchChange}
                      name="public"
                      color="primary"
                    />
                  }
                  label="Public League"
                />
                <FormHelperText>
                  {formValues.public 
                    ? 'Anyone can find and join this league' 
                    : 'Only invited users can join this league'}
                </FormHelperText>
              </FormControl>
            </Grid>
          </Grid>
        );
    case 1:
         // Calendar step
         return (
            <Box>
              <Box sx={{ mb: 3 }}>
                <Typography variant="h6" gutterBottom>Race Calendar</Typography>
                <Typography variant="body2" color="text.secondary">
                  Add races to your league calendar. You can add more races later.
                </Typography>
              </Box>
              
              <Grid container spacing={2} sx={{ mb: 3 }}>
                <Grid item xs={12} md={6}>
                  <TextField
                    label="Track Name"
                    fullWidth
                    value={trackInput}
                    onChange={(e) => setTrackInput(e.target.value)}
                    placeholder="e.g. Monza, Spa-Francorchamps"
                  />
                </Grid>
                <Grid item xs={12} md={6}>
                  <TextField
                    label="Race Date & Time"
                    type="datetime-local"
                    fullWidth
                    value={dateInput}
                    onChange={(e) => setDateInput(e.target.value)}
                    InputLabelProps={{ shrink: true }}
                  />
                </Grid>
                <Grid item xs={12}>
                  <Button 
                    variant="outlined" 
                    startIcon={<AddIcon />}
                    onClick={addRace}
                    disabled={!trackInput.trim() || !dateInput}
                  >
                    Add Race
                  </Button>
                </Grid>
              </Grid>
              
              {formValues.calendar.length > 0 ? (
                <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
                  <Typography variant="subtitle1" gutterBottom>
                    Scheduled Races ({formValues.calendar.length})
                  </Typography>
                  <TableContainer>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>Track</TableCell>
                          <TableCell>Date</TableCell>
                          <TableCell align="right">Actions</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {formValues.calendar
                          .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
                          .map((race, index) => (
                          <TableRow key={index}>
                            <TableCell>{race.track}</TableCell>
                            <TableCell>
                              {new Date(race.date).toLocaleDateString()} {new Date(race.date).toLocaleTimeString()}
                            </TableCell>
                            <TableCell align="right">
                              <IconButton 
                                size="small" 
                                color="error"
                                onClick={() => removeRace(index)}
                              >
                                <DeleteIcon />
                              </IconButton>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </Paper>
              ) : (
                <Alert severity="info" sx={{ mb: 2 }}>
                  No races added yet. You can still create the league and add races later.
                </Alert>
              )}
            </Box>
          );
          
        case 2: // Scoring System (updated)
          return (
            <Box>
              <Box sx={{ mb: 3 }}>
                <Typography variant="h6" gutterBottom>
                  Scoring System
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Set the points awarded for each finishing position.
                </Typography>
              </Box>
              
              <Grid container spacing={2} sx={{ mb: 3 }}>
                <Grid item xs={12} md={6}>
                  <TextField
                    name="fastestLapPoint"
                    label="Points for Fastest Lap"
                    type="number"
                    fullWidth
                    value={formValues.fastestLapPoint}
                    onChange={handleInputChange}
                    error={Boolean(errors.fastestLapPoint)}
                    helperText={errors.fastestLapPoint || 'Extra points for setting the fastest lap (0 to disable)'}
                    inputProps={{ min: 0 }}
                  />
                </Grid>
                <Grid item xs={12} md={6} sx={{ display: 'flex', alignItems: 'center' }}>
                  <FormControl fullWidth>
                    <InputLabel id="scoring-preset-label">Use Preset</InputLabel>
                    <Select
                      labelId="scoring-preset-label"
                      label="Use Preset"
                      value=""
                      onChange={(e) => {
                        if (e.target.value === 'f1') {
                          setFormValues({
                            ...formValues,
                            pointSystem: {...defaultPointSystem}
                          });
                        } else if (e.target.value === 'f1-2010') {
                          setFormValues({
                            ...formValues,
                            pointSystem: {
                              "1": 25, "2": 20, "3": 15, "4": 10, 
                              "5": 8, "6": 6, "7": 4, "8": 3, "9": 2, "10": 1
                            }
                          });
                        }
                      }}
                    >
                      <MenuItem value=""><em>Select a preset (optional)</em></MenuItem>
                      <MenuItem value="f1">F1 Current (25, 18, 15, ...)</MenuItem>
                      <MenuItem value="f1-2010">F1 2010-2018 (25, 20, 15, ...)</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>
              </Grid>
              
              <Typography variant="subtitle1" sx={{ mb: 2 }}>
                Points Per Position
                {errors.pointSystem && (
                  <Typography color="error" variant="caption" sx={{ ml: 1 }}>
                    {errors.pointSystem}
                  </Typography>
                )}
              </Typography>
              
              <Paper 
                variant="outlined" 
                sx={{ p: 2, mb: 2, bgcolor: 'background.paper', borderRadius: 1 }}
              >
                <Grid container spacing={2}>
                  {Object.entries(formValues.pointSystem)
                    .sort((a, b) => parseInt(a[0]) - parseInt(b[0]))
                    .map(([position, points]) => (
                    <Grid item xs={12} sm={6} md={4} key={position}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <TextField
                          label={`Position ${position}`}
                          type="number"
                          value={points}
                          onChange={(e) => updatePointValue(position, parseInt(e.target.value, 10) || 0)}
                          fullWidth
                          size="small"
                          InputProps={{ inputProps: { min: 0 } }}
                        />
                        <IconButton 
                          size="small" 
                          color="error"
                          onClick={() => removePointPosition(position)}
                        >
                          <DeleteIcon />
                        </IconButton>
                      </Box>
                    </Grid>
                  ))}
                </Grid>
              </Paper>
              
              <Button 
                startIcon={<AddIcon />}
                onClick={addPointPosition}
                variant="outlined"
                sx={{ mt: 1 }}
              >
                Add Position
              </Button>
            </Box>
          );
          
      case 3: // Invites step (formerly Participants step)
      return (
        <Box>
          <Box sx={{ mb: 3 }}>
            <Typography variant="h6" gutterBottom>Invite Players</Typography>
            <Typography variant="body2" color="text.secondary">
              Invite players to join your league. They'll receive an email invitation.
            </Typography>
          </Box>

          {/* Creator participation toggle */}
          <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
            <FormControlLabel
              control={
                <Switch
                  checked={formValues.creatorParticipates}
                  onChange={(e) => setFormValues({
                    ...formValues,
                    creatorParticipates: e.target.checked
                  })}
                  color="primary"
                />
              }
              label="I want to participate in this league"
            />
            <FormHelperText>
              {formValues.creatorParticipates 
                ? "You'll be added as a driver in this league" 
                : "You'll only be the league administrator, not a driver"}
            </FormHelperText>
          </Paper>
          
          <Grid container spacing={2} sx={{ mb: 3 }}>
            <Grid item xs={12} sm={9}>
              <TextField
                label="Email Address"
                fullWidth
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                placeholder="player@example.com"
                type="email"
              />
            </Grid>
            <Grid item xs={12} sm={3}>
              <Button 
                variant="contained" 
                startIcon={<AddIcon />}
                onClick={addInvite}
                disabled={!inviteEmail.trim() || !inviteEmail.includes('@')}
                sx={{ height: '100%' }}
                fullWidth
              >
                Invite
              </Button>
            </Grid>
          </Grid>
          
          {formValues.invites.length > 0 ? (
            <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
              <Typography variant="subtitle1" gutterBottom>
                Players to Invite ({formValues.invites.length})
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {formValues.invites.map((email) => (
                  <Chip
                    key={email}
                    label={email}
                    onDelete={() => removeInvite(email)}
                    size="medium"
                  />
                ))}
              </Box>
            </Paper>
          ) : (
            <Alert severity="info">
              No invitations added yet. You can still create the league and invite people later.
            </Alert>
          )}
        </Box>
      );
      
    case 4: // Review step (updated)
      return (
        <Box>
          <Alert severity="info" sx={{ mb: 3 }}>
            Please review your league configuration before creating. You can make changes later as an admin.
          </Alert>
          
          <Paper variant="outlined" sx={{ p: 3, mb: 3 }}>
            <Grid container spacing={3}>
              <Grid item xs={12} md={6}>
                <Typography variant="subtitle2" color="text.secondary">League Name</Typography>
                <Typography variant="body1" sx={{ mb: 2 }}>{formValues.name}</Typography>
                
                <Typography variant="subtitle2" color="text.secondary">Maximum Players</Typography>
                <Typography variant="body1" sx={{ mb: 2 }}>{formValues.max_players}</Typography>
                
                <Typography variant="subtitle2" color="text.secondary">League Type</Typography>
                <Typography variant="body1" sx={{ mb: 2 }}>
                  {formValues.public ? 'Public' : 'Private'} League
                </Typography>
                
                <Typography variant="subtitle2" color="text.secondary">Owner</Typography>
                <Typography variant="body1" sx={{ mb: 2 }}>
                  {user?.email || 'You'} {formValues.creatorParticipates && " (Participating)"}
                </Typography>
              </Grid>
              
              <Grid item xs={12} md={6}>
                <Typography variant="subtitle2" color="text.secondary">Points for Fastest Lap</Typography>
                <Typography variant="body1" sx={{ mb: 2 }}>{formValues.fastestLapPoint}</Typography>
                
                <Typography variant="subtitle2" color="text.secondary">Points System</Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: 1, mb: 2 }}>
                  {Object.entries(formValues.pointSystem)
                    .sort((a, b) => parseInt(a[0]) - parseInt(b[0]))
                    .map(([position, points]) => (
                    <Chip 
                      key={position} 
                      label={`P${position}: ${points}`} 
                      size="small"
                      variant="outlined" 
                    />
                  ))}
                </Box>
                
                <Typography variant="subtitle2" color="text.secondary">Invitations</Typography>
                <Typography variant="body1" sx={{ mb: 2 }}>
                  {formValues.invites.length > 0 
                    ? `${formValues.invites.length} players will be invited` 
                    : 'No invitations (you can invite players later)'}
                </Typography>
              </Grid>
            </Grid>
            
            {/* Calendar summary - no changes needed */}
            <Divider sx={{ my: 2 }} />
            <Typography variant="subtitle2" color="text.secondary">Race Calendar</Typography>
            {/* ... existing calendar table code ... */}
          </Paper>
          
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Typography>
              Creator: <strong>{user?.name || 'You'}</strong>
            </Typography>
            <Chip label="League Owner" color="primary" size="small" />
            {formValues.creatorParticipates && <Chip label="Participant" color="success" size="small" />}
          </Box>
        </Box>
      );
    default:
        return null;
    }
  };
  
  return (
    <Box 
      sx={{ 
        backgroundColor: 'background.default',
        minHeight: '100vh',
        pt: 4,
        pb: 8,
      }}
    >
      <Container maxWidth="md">
        {/* Header with back button */}
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 4 }}>
          <IconButton onClick={() => navigate('/leagues')} sx={{ mr: 2 }}>
            <ArrowBackIcon />
          </IconButton>
          <Typography variant="h4" component="h1" sx={{ fontWeight: 600 }}>
            Create New League
          </Typography>
        </Box>
        
        {/* Main content area */}
        <Paper 
          sx={{ 
            p: 4, 
            mb: 4,
            backgroundImage: 'linear-gradient(180deg, rgba(30,30,30,0.7) 0%, rgba(20,20,20,0.9) 100%)',
          }}
        >
          {/* Error message */}
          {error && <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert>}
          
          {/* Success message */}
          {success && (
            <Alert 
              severity="success" 
              sx={{ mb: 3 }}
              icon={<CheckIcon fontSize="inherit" />}
            >
              League created successfully! Redirecting...
            </Alert>
          )}
          
          {/* Stepper */}
          <Stepper activeStep={activeStep} alternativeLabel sx={{ mb: 4 }}>
            {steps.map((label) => (
              <Step key={label}>
                <StepLabel>{label}</StepLabel>
              </Step>
            ))}
          </Stepper>
          
          {/* Step content */}
          <Box sx={{ mb: 4 }}>
            {renderStepContent(activeStep)}
          </Box>
          
          {/* Navigation buttons */}
          <Divider sx={{ my: 3 }} />
          <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
            <Button
              disabled={activeStep === 0 || isLoading}
              onClick={handleBack}
              variant="text"
            >
              Back
            </Button>
            <Box>
              {activeStep === steps.length - 1 ? (
                <Button
                  variant="contained"
                  color="primary"
                  onClick={handleSubmit}
                  disabled={isLoading || success}
                >
                  {isLoading ? <CircularProgress size={24} color="inherit" /> : 'Create League'}
                </Button>
              ) : (
                <Button
                  variant="contained"
                  onClick={handleNext}
                >
                  Next
                </Button>
              )}
            </Box>
          </Box>
        </Paper>
        
        {/* Helper box */}
        <Paper
          sx={{
            p: 3,
            display: 'flex',
            alignItems: 'flex-start',
            gap: 2,
            bgcolor: 'background.paper',
          }}
        >
          <HelpIcon color="primary" />
          <Box>
            <Typography variant="subtitle1" gutterBottom>
              What's Next?
            </Typography>
            <Typography variant="body2" color="text.secondary">
              After creating your league, you'll be able to invite players, add races to your calendar, and start tracking results. As the league owner, you'll have full admin capabilities.
            </Typography>
          </Box>
        </Paper>
      </Container>
    </Box>
  );
};

export default CreateLeague;