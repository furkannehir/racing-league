import React, { useState, useEffect, useLayoutEffect, useRef } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  FormControlLabel,
  Switch,
  Checkbox,
  CircularProgress,
  Alert,
  Box,
  Chip,
  Tooltip,
  IconButton,
  List,
  ListItem,
  ListItemText,
  Card,
  Avatar,
  Paper,
  Divider,
} from '@mui/material';
import {
  Info as InfoIcon,
  EmojiEvents as TrophyIcon,
  Speed as SpeedIcon,
  Close as CloseIcon,
  DragIndicator as DragIcon,
  CloudUpload as UploadIcon,
  AutoAwesome as AIIcon,
  Delete as DeleteIcon,
} from '@mui/icons-material';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { submitRaceResult, processMultipleRaceScreenshots } from '../services/api';
import { League, RaceDetails } from '../types/league';
import { importImageResults, validateScreenshots, ImageDriverResult as DriverResult } from '../services/race-image-import';

interface SubmitRaceResultsDialogProps {
  open: boolean;
  onClose: () => void;
  league: League;
  selectedRace: RaceDetails | null;
  onResultsSubmitted: (updatedLeague: League) => void;
}

// Sortable driver item component
const SortableDriverItem = ({ 
  driver, 
  totalPoints,
  onDNFChange, 
  onFastestLapChange,
  disabled,
}: {
  driver: DriverResult;
  totalPoints: number;
  onDNFChange: (driverId: string, isDNF: boolean) => void;
  onFastestLapChange: (driverId: string) => void;
  disabled: boolean;
}) => {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging
  } = useSortable({ id: driver.driverId, disabled: disabled || driver.dnf });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : undefined,
    zIndex: isDragging ? 1000 : 1,
  };

  return (
    <ListItem
      ref={setNodeRef}
      style={style}
      disablePadding
      sx={{ 
        display: 'block',
        mb: 1,
        mx: 1,
        bgcolor: isDragging 
          ? 'rgba(30, 144, 255, 0.1)' 
          : driver.fastestLap 
            ? 'rgba(156, 39, 176, 0.1)' 
            : 'transparent',
      }}
    >
      <Card
        sx={{ 
          p: 2,
          opacity: driver.dnf ? 0.6 : 1,
          border: '1px solid rgba(255,255,255,0.1)',
          borderLeft: driver.position <= 3 
            ? `4px solid ${
                driver.position === 1 
                  ? 'gold' 
                  : driver.position === 2 
                    ? 'silver' 
                    : '#cd7f32'
              }` 
            : undefined,
          '&:hover': {
            bgcolor: !driver.dnf ? 'rgba(30, 144, 255, 0.05)' : undefined,
            border: '1px solid rgba(255,255,255,0.2)',
          }
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', width: '100%' }}>
          <Box 
            {...attributes}
            {...listeners}
            sx={{ 
              mr: 2, 
              display: 'flex', 
              alignItems: 'center',
              color: 'text.secondary',
              cursor: driver.dnf ? 'not-allowed' : 'grab',
            }}
          >
            <DragIcon />
          </Box>
          
          <Avatar 
            sx={{ 
              bgcolor: 'primary.main', 
              color: 'white',
              width: 36,
              height: 36,
              mr: 2,
              fontWeight: 'bold'
            }}
          >
            {driver.position}
          </Avatar>
          
          <ListItemText 
            primary={driver.name}
            primaryTypographyProps={{
              fontWeight: 500,
              sx: {
                textDecoration: driver.dnf ? 'line-through' : 'none'
              }
            }}
            secondary={`Points: ${totalPoints}`}
          />
          
          <Box sx={{ display: 'flex', alignItems: 'center', ml: 2 }}>
            {driver.fastestLap && (
              <Tooltip title="Fastest Lap">
                <SpeedIcon 
                  color="secondary" 
                  sx={{ mr: 2 }}
                />
              </Tooltip>
            )}
            
            <FormControlLabel
              control={
                <Switch
                  checked={driver.fastestLap}
                  onChange={() => onFastestLapChange(driver.driverId)}
                  size="small"
                  color="secondary"
                  disabled={disabled || driver.dnf}
                />
              }
              label="Fastest Lap"
              sx={{ mr: 2 }}
            />
            
            <FormControlLabel
              control={
                <Switch
                  checked={driver.dnf}
                  disabled={disabled}
                  onChange={(e) => onDNFChange(driver.driverId, e.target.checked)}
                  size="small"
                />
              }
              label="DNF"
            />
          </Box>
        </Box>
      </Card>
    </ListItem>
  );
};

const SubmitRaceResultsDialog: React.FC<SubmitRaceResultsDialogProps> = ({
  open,
  onClose,
  league,
  selectedRace,
  onResultsSubmitted
}) => {
  const [driverResults, setDriverResults] = useState<DriverResult[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadedImages, setUploadedImages] = useState<File[]>([]);
  const [processingImages, setProcessingImages] = useState(false);
  const [imagePreviews, setImagePreviews] = useState<string[]>([]);
  const [importSummary, setImportSummary] = useState<string | null>(null);
  const [reviewed, setReviewed] = useState(false);
  const generation = useRef(0);
  const operationPending = useRef(false);
  const busy = processingImages || submitting;
  
  // Set up sensors for drag and drop
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8, // 8px movement required before activating drag
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );
  
  const pointSystem = league.pointSystem as Record<string, number> || {};
  const raceId = selectedRace?._id;
  const rosterKey = JSON.stringify((league.participants || []).map((driver, index) => ({
    position: index + 1, fastestLap: false, dnf: false, driverId: driver.email,
    name: driver.league_user_name || driver.name || league.standings?.overall?.[driver.email]?.name || driver.email,
  })));
  const participantKey = JSON.stringify(league.participants);

  useLayoutEffect(() => {
    const context = generation;
    context.current++;
    operationPending.current = false;
    setDriverResults(open && raceId ? JSON.parse(rosterKey) : []);
    setUploadedImages([]);
    setProcessingImages(false);
    setSubmitting(false);
    setImportSummary(null);
    setReviewed(false);
    setError(null);
    return () => { context.current++; };
  }, [open, league._id, raceId, rosterKey, participantKey]);

  useEffect(() => {
    const previews = open ? uploadedImages.map(file => URL.createObjectURL(file)) : [];
    setImagePreviews(previews);
    return () => { previews.forEach(url => URL.revokeObjectURL(url)); };
  }, [open, uploadedImages]);

  const handleClose = () => {
    generation.current++;
    onClose();
  };

  const handleImageUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || []);
    event.target.value = '';
    if (operationPending.current || !files.length) return;
    const validation = validateScreenshots([...uploadedImages, ...files]);
    if (validation) { setError(validation); return; }
    setUploadedImages(prev => [...prev, ...files]);
    setError(null);
  };

  const removeImage = (index: number) => {
    if (operationPending.current) return;
    setUploadedImages(prev => prev.filter((_, i) => i !== index));
  };

  const processImageWithAI = async () => {
    if (!open || !uploadedImages.length || !selectedRace || operationPending.current) return;
    const requestGeneration = generation.current;
    operationPending.current = true;
    setProcessingImages(true);
    setError(null);
    try {
      const response = await processMultipleRaceScreenshots(uploadedImages, league._id, selectedRace._id);
      if (generation.current !== requestGeneration) return;
      const imported = importImageResults(response, driverResults, league.participants);
      setDriverResults(imported.drivers);
      setImportSummary([
        `AI identified ${imported.matched} of ${driverResults.length} drivers. Review every position, DNF, and fastest lap before submitting.`,
        ...imported.warnings,
      ].join(' '));
      setReviewed(false);
    } catch (err: unknown) {
      if (generation.current === requestGeneration) {
        setError(err instanceof Error ? err.message : 'Failed to process images. Please try again.');
      }
    } finally {
      if (generation.current === requestGeneration) {
        operationPending.current = false;
        setProcessingImages(false);
      }
    }
  };

  const handleDNFChange = (driverId: string, isDNF: boolean) => {
    if (operationPending.current) return;
    setReviewed(false);
    setDriverResults(prev => 
      prev.map(driver => {
        if (driver.driverId === driverId) {
          return { 
            ...driver, 
            dnf: isDNF,
            // If DNF, reset fastest lap to false
            fastestLap: isDNF ? false : driver.fastestLap
          };
        }
        return driver;
      })
    );
  };

  const handleFastestLapChange = (driverId: string) => {
    if (operationPending.current) return;
    setReviewed(false);
    setDriverResults(prev => 
      prev.map(driver => ({ ...driver,
        fastestLap: driver.driverId === driverId && !driver.dnf && !driver.fastestLap,
      }))
    );
  };

  const calculatePoints = (position: number, fastestLap: boolean, dnf: boolean): number => {
    if (dnf) return 0;
    
    const positionPoints = pointSystem[position.toString()] || 0;
    const fastestLapPoints = fastestLap ? league.fastestLapPoint : 0;
    return positionPoints + fastestLapPoints;
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (operationPending.current || !over || active.id === over.id) return;
    setReviewed(false);
    
    if (active.id !== over?.id) {
      setDriverResults((prev) => {
        const oldIndex = prev.findIndex(driver => driver.driverId === active.id);
        const newIndex = prev.findIndex(driver => driver.driverId === over?.id);
        if (oldIndex < 0 || newIndex < 0) return prev;
        
        const reorderedDrivers = arrayMove(prev, oldIndex, newIndex);
        
        // Update positions based on new order
        return reorderedDrivers.map((driver, index) => ({
          ...driver,
          position: index + 1
        }));
      });
    }
  };

  const handleSubmit = async () => {
    if (!open || !selectedRace || !league._id || operationPending.current || (importSummary && !reviewed)) return;
    const requestGeneration = generation.current;
    operationPending.current = true;
    
    try {
      setSubmitting(true);
      setError(null);
      
      // Format the results to match the API expectations
      const formattedResults: Record<string, { position: number; fastestLap?: boolean; points: number; dnf?: boolean }> = {};
      
      // Calculate points based on position and pointSystem
      driverResults.forEach(driver => {
        const { position, fastestLap, dnf, driverId } = driver;
        const points = calculatePoints(position, fastestLap, dnf);
        
        formattedResults[driverId] = {
          position,
          points,
          ...(fastestLap && { fastestLap: true }),
          ...(dnf && { dnf: true })
        };
      });
      
      // Call API to submit race results
      const updatedLeague = await submitRaceResult(
        league._id, 
        selectedRace._id, 
        formattedResults
      );
      if (generation.current !== requestGeneration) return;
      
      // Notify parent component
      onResultsSubmitted(updatedLeague);
      
      // Close dialog
      handleClose();
      
    } catch (err: unknown) {
      if (generation.current === requestGeneration) {
        setError(err instanceof Error ? err.message : 'Failed to submit race results. Please try again.');
      }
    } finally {
      if (generation.current === requestGeneration) {
        operationPending.current = false;
        setSubmitting(false);
      }
    }
  };

  if (!selectedRace) return null;

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: {
          bgcolor: 'rgba(30,30,30,0.95)',
          backgroundImage: 'linear-gradient(180deg, rgba(30,30,30,0.9) 0%, rgba(25,25,25,1) 100%)',
        }
      }}
    >
      <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <TrophyIcon sx={{ mr: 1, color: 'primary.main' }} />
          Submit Race Results: {selectedRace.track}
        </Box>
        <IconButton onClick={handleClose} size="small" aria-label="Close results dialog">
          <CloseIcon />
        </IconButton>
      </DialogTitle>
      <DialogContent>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}
        
        {/* Image Upload Section */}
        <Paper 
          elevation={2} 
          sx={{ 
            p: 3, 
            mb: 3, 
            border: '2px dashed',
            borderColor: uploadedImages.length > 0 ? 'primary.main' : 'grey.500',
            bgcolor: uploadedImages.length > 0 ? 'primary.light' : 'background.paper',
            opacity: uploadedImages.length > 0 ? 0.9 : 1,
          }}
        >
          <Typography variant="h6" sx={{ mb: 2, display: 'flex', alignItems: 'center' }}>
            <AIIcon sx={{ mr: 1 }} />
            AI-Powered Results Generation
          </Typography>
          
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Upload up to 2 JPEG or PNG screenshots, up to 6 MiB each. AI suggests positions for your review;
            check every driver, DNF, and fastest lap before saving.
          </Typography>
          
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <input
              accept="image/jpeg,image/png,image/jpg"
              style={{ display: 'none' }}
              id="race-screenshot-upload"
              type="file"
              onChange={handleImageUpload}
              multiple
              disabled={busy || uploadedImages.length >= 2}
            />
            <label htmlFor="race-screenshot-upload">
              <Button
                variant="outlined"
                component="span"
                startIcon={<UploadIcon />}
                fullWidth
                sx={{ height: 48 }}
                disabled={busy || uploadedImages.length >= 2}
              >
                {uploadedImages.length >= 2 
                  ? 'Maximum 2 screenshots reached' 
                  : uploadedImages.length > 0 
                    ? `Add Screenshots (${uploadedImages.length}/2 uploaded)` 
                    : 'Upload Race Screenshots (Max 2)'}
              </Button>
            </label>
            
            {imagePreviews.length > 0 && (
              <Box sx={{ mt: 2 }}>
                <Typography variant="subtitle2" sx={{ mb: 2 }}>
                  Uploaded Screenshots ({imagePreviews.length}):
                </Typography>
                <Box sx={{ 
                  display: 'grid', 
                  gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
                  gap: 2 
                }}>
                  {imagePreviews.map((preview, index) => (
                    <Box key={index} sx={{ position: 'relative' }}>
                      <img 
                        src={preview} 
                        alt={`Race screenshot ${index + 1}`} 
                        style={{ 
                          width: '100%', 
                          height: '120px', 
                          objectFit: 'cover',
                          borderRadius: '8px'
                        }} 
                      />
                      <IconButton
                        size="small"
                        onClick={() => removeImage(index)}
                        disabled={busy}
                        aria-label={`Remove screenshot ${index + 1}`}
                        sx={{
                          position: 'absolute',
                          top: 4,
                          right: 4,
                          bgcolor: 'rgba(0,0,0,0.7)',
                          color: 'white',
                          '&:hover': {
                            bgcolor: 'rgba(0,0,0,0.9)',
                          }
                        }}
                      >
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </Box>
                  ))}
                </Box>
              </Box>
            )}
            
            {uploadedImages.length > 0 && (
              <Button
                variant="contained"
                color="primary"
                startIcon={processingImages ? <CircularProgress size={20} /> : <AIIcon />}
                onClick={processImageWithAI}
                disabled={busy}
                sx={{ mt: 1 }}
              >
                {processingImages ? `Analyzing ${uploadedImages.length} Screenshot${uploadedImages.length > 1 ? 's' : ''}...` : `Extract Results from ${uploadedImages.length} Screenshot${uploadedImages.length > 1 ? 's' : ''}`}
              </Button>
            )}
          </Box>
        </Paper>
        
        <Divider sx={{ mb: 3 }} />
        {importSummary && (
          <Box sx={{ mb: 3 }}>
            <Alert severity="warning">{importSummary}</Alert>
            <FormControlLabel
              control={<Checkbox checked={reviewed} disabled={busy} onChange={event => setReviewed(event.target.checked)} />}
              label="I have reviewed the driver order, DNF, and fastest lap."
            />
          </Box>
        )}
        
        <Box sx={{ mb: 3 }}>
          <Typography variant="body2" color="text.secondary" paragraph>
            Drag and drop drivers to reorder them based on race results. Mark DNF for drivers who did not finish.
            Only one driver can have the fastest lap.
          </Typography>
          
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
            <Tooltip title="Points awarded per position">
              <Box>
                <Chip
                  icon={<InfoIcon />}
                  label="Points System"
                  variant="outlined"
                  color="info"
                  size="small"
                />
              </Box>
            </Tooltip>
            {Object.entries(pointSystem)
              .sort((a, b) => Number(a[0]) - Number(b[0]))
              .map(([pos, points]) => (
                <Chip 
                  key={pos}
                  label={`P${pos}: ${points} pts`}
                  size="small"
                  variant="outlined"
                />
              ))}
            {league.fastestLapPoint > 0 && (
              <Chip 
                icon={<SpeedIcon fontSize="small" />}
                label={`Fastest Lap: ${league.fastestLapPoint} pts`}
                size="small"
                color="secondary"
              />
            )}
          </Box>
        </Box>
        
        <DndContext 
          sensors={sensors} 
          collisionDetection={closestCenter} 
          onDragEnd={handleDragEnd}
        >
          <SortableContext 
            items={driverResults.map(driver => driver.driverId)} 
            strategy={verticalListSortingStrategy}
          >
            <List
              sx={{ 
                bgcolor: 'background.paper', 
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: 1,
                maxHeight: '60vh',
                overflow: 'auto'
              }}
            >
              {driverResults.map((driver) => {
                const totalPoints = calculatePoints(
                  driver.position, 
                  driver.fastestLap, 
                  driver.dnf
                );
                
                return (
                  <SortableDriverItem 
                    key={driver.driverId} 
                    driver={driver} 
                    totalPoints={totalPoints}
                    onDNFChange={handleDNFChange}
                    onFastestLapChange={handleFastestLapChange}
                    disabled={busy}
                  />
                );
              })}
            </List>
          </SortableContext>
        </DndContext>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 3 }}>
        <Button 
          onClick={handleClose}
          variant="outlined"
        >
          Cancel
        </Button>
        <Button 
          onClick={handleSubmit} 
          variant="contained" 
          color="primary"
          disabled={busy || driverResults.length === 0 || (!!importSummary && !reviewed)}
          startIcon={submitting && <CircularProgress size={20} />}
        >
          {submitting ? 'Submitting...' : 'Submit Results'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default SubmitRaceResultsDialog;
