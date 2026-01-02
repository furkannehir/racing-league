import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  FormControlLabel,
  Switch,
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
import { submitRaceResult, processRaceScreenshot, processMultipleRaceScreenshots } from '../services/api';
import { League, RaceDetails, LeagueParticipant } from '../types/league';

interface SubmitRaceResultsDialogProps {
  open: boolean;
  onClose: () => void;
  league: League;
  selectedRace: RaceDetails | null;
  onResultsSubmitted: (updatedLeague: League) => void;
}

interface DriverResult {
  position: number;
  fastestLap: boolean;
  dnf: boolean;
  driverId: string;
  name: string;
}

// Sortable driver item component
const SortableDriverItem = ({ 
  driver, 
  totalPoints,
  onDNFChange, 
  onFastestLapChange 
}: {
  driver: DriverResult;
  totalPoints: number;
  onDNFChange: (driverId: string, isDNF: boolean) => void;
  onFastestLapChange: (driverId: string) => void;
}) => {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging
  } = useSortable({ id: driver.driverId, disabled: driver.dnf });

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
                  disabled={driver.dnf}
                />
              }
              label="Fastest Lap"
              sx={{ mr: 2 }}
            />
            
            <FormControlLabel
              control={
                <Switch
                  checked={driver.dnf}
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
  
  const standings = league.standings?.overall || {};
  const pointSystem = league.pointSystem as Record<string, number> || {};

  useEffect(() => {
    if (open && selectedRace && league.participants) {
      // Initialize driver results when dialog opens
      const initialResults: DriverResult[] = Array.isArray(league.participants) 
        ? league.participants.map((driver: LeagueParticipant, index) => {
            const driverId = driver.email;
            // Prioritize league_user_name over standings name
            const name = driver.league_user_name || driver.name || standings[driverId]?.name || driver.email;
            return { 
              position: index + 1,
              fastestLap: false,
              dnf: false,
              driverId,
              name
            };
          })
        : [];
      
      setDriverResults(initialResults);
      // Reset upload state when dialog opens
      setUploadedImages([]);
      setImagePreviews([]);
      setError(null);
    }
  }, [open, selectedRace, league.participants, standings]);

  const handleImageUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (files && files.length > 0) {
      const newFiles = Array.from(files);
      
      // Validate file types (only JPEG and PNG as per backend)
      const validFiles = newFiles.filter(file => 
        file.type === 'image/jpeg' || file.type === 'image/png' || file.type === 'image/jpg'
      );
      
      if (validFiles.length !== newFiles.length) {
        setError('Only JPEG and PNG files are supported. Some files were ignored.');
      }
      
      // Limit to 2 images total as per backend constraint
      const currentCount = uploadedImages.length;
      const availableSlots = 2 - currentCount;
      const filesToAdd = validFiles.slice(0, availableSlots);
      
      if (validFiles.length > availableSlots) {
        setError(`Maximum 2 images allowed. Only the first ${availableSlots} image(s) were added.`);
      }
      
      setUploadedImages(prev => [...prev, ...filesToAdd]);
      
      // Create previews for new files
      filesToAdd.forEach(file => {
        const reader = new FileReader();
        reader.onload = (e) => {
          setImagePreviews(prev => [...prev, e.target?.result as string]);
        };
        reader.readAsDataURL(file);
      });
      
      // Clear error if we successfully added files and no validation issues
      if (filesToAdd.length > 0 && validFiles.length <= availableSlots && validFiles.length === newFiles.length) {
        setError(null);
      }
    }
  };

  const removeImage = (index: number) => {
    setUploadedImages(prev => prev.filter((_, i) => i !== index));
    setImagePreviews(prev => prev.filter((_, i) => i !== index));
  };

  const processImageWithAI = async () => {
    if (!uploadedImages.length || !selectedRace) return;

    setProcessingImages(true);
    setError(null);

    try {
      let response;
      
      if (uploadedImages.length === 1) {
        // Use single image API for one image
        response = await processRaceScreenshot(
          uploadedImages[0],
          league._id,
          selectedRace._id
        );
      } else {
        // Use multiple images API for efficiency
        response = await processMultipleRaceScreenshots(
          uploadedImages,
          league._id,
          selectedRace._id
        );
      }
      
      // Parse the response if it's a string (OpenAI returns JSON string)
      let extractedResults: any[] = [];
      if (typeof response === 'string') {
        try {
          extractedResults = JSON.parse(response);
        } catch (parseError) {
          console.error('Failed to parse AI response:', parseError);
          setError('Failed to parse AI response. Please try again.');
          return;
        }
      } else if (Array.isArray(response)) {
        extractedResults = response;
      } else if (response?.results && Array.isArray(response.results)) {
        extractedResults = response.results;
      }
      
      // Map extracted results to driver results
      if (extractedResults.length > 0) {
        const updatedResults = driverResults.map(driver => {
          // Try to match by driver name (case-insensitive)
          const aiResult = extractedResults.find((result: any) => 
            result.driver && 
            driver.name.toLowerCase().includes(result.driver.toLowerCase()) ||
            result.driver.toLowerCase().includes(driver.name.toLowerCase())
          );
          
          if (aiResult && aiResult.position) {
            return {
              ...driver,
              position: aiResult.position,
              dnf: false, // Set default values since API doesn't provide these
              fastestLap: false,
            };
          }
          return driver;
        });
        
        // Sort by position and update remaining positions
        const sortedResults = updatedResults.sort((a, b) => a.position - b.position);
        const finalResults = sortedResults.map((driver, index) => ({
          ...driver,
          position: driver.position || index + 1 // Ensure all drivers have positions
        }));
        
        setDriverResults(finalResults);
      } else {
        setError('No race results were extracted from the images. Please check the image quality and try again.');
      }
    } catch (err: any) {
      console.error('Error processing images:', err);
      setError(err?.response?.data?.message || err?.message || 'Failed to process images');
    } finally {
      setProcessingImages(false);
    }
  };

  const handleDNFChange = (driverId: string, isDNF: boolean) => {
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
    setDriverResults(prev => 
      prev.map(driver => ({
        ...driver,
        // Clear all fastest laps first
        fastestLap: false
      })).map(driver => {
        // Then set fastest lap for the selected driver if not DNF
        if (driver.driverId === driverId && !driver.dnf) {
          return { ...driver, fastestLap: true };
        }
        return driver;
      })
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
    
    if (active.id !== over?.id) {
      setDriverResults((prev) => {
        const oldIndex = prev.findIndex(driver => driver.driverId === active.id);
        const newIndex = prev.findIndex(driver => driver.driverId === over?.id);
        
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
    if (!selectedRace || !league._id) return;
    
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
      
      // Notify parent component
      onResultsSubmitted(updatedLeague);
      
      // Close dialog
      onClose();
      
    } catch (err: any) {
      setError(err?.response?.data?.message || 'Failed to submit race results. Please try again.');
      console.error('Error submitting race results:', err);
    } finally {
      setSubmitting(false);
    }
  };

  if (!selectedRace) return null;

  return (
    <Dialog
      open={open}
      onClose={onClose}
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
        <IconButton onClick={onClose} size="small">
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
            Upload up to 2 screenshots of the race results and let AI automatically generate the race positions for you.
          </Typography>
          
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <input
              accept="image/jpeg,image/png,image/jpg"
              style={{ display: 'none' }}
              id="race-screenshot-upload"
              type="file"
              onChange={handleImageUpload}
              multiple
              disabled={uploadedImages.length >= 2}
            />
            <label htmlFor="race-screenshot-upload">
              <Button
                variant="outlined"
                component="span"
                startIcon={<UploadIcon />}
                fullWidth
                sx={{ height: 48 }}
                disabled={uploadedImages.length >= 2}
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
                disabled={processingImages}
                sx={{ mt: 1 }}
              >
                {processingImages ? `Analyzing ${uploadedImages.length} Screenshot${uploadedImages.length > 1 ? 's' : ''}...` : `Extract Results from ${uploadedImages.length} Screenshot${uploadedImages.length > 1 ? 's' : ''}`}
              </Button>
            )}
          </Box>
        </Paper>
        
        <Divider sx={{ mb: 3 }} />
        
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
                  />
                );
              })}
            </List>
          </SortableContext>
        </DndContext>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 3 }}>
        <Button 
          onClick={onClose}
          variant="outlined"
        >
          Cancel
        </Button>
        <Button 
          onClick={handleSubmit} 
          variant="contained" 
          color="primary"
          disabled={submitting}
          startIcon={submitting && <CircularProgress size={20} />}
        >
          {submitting ? 'Submitting...' : 'Submit Results'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default SubmitRaceResultsDialog;