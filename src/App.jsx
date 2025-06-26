import { useState, useEffect } from 'react';
import { AgGridReact } from 'ag-grid-react';
import { ModuleRegistry, AllCommunityModule } from 'ag-grid-community';
import axios from 'axios';
import {
  Container,
  Grid,
  Card,
  CardContent,
  Typography,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Box,
  Chip,
  Paper,
  AppBar,
  Toolbar,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Divider,
  Avatar,
  Autocomplete
} from '@mui/material';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import L from 'leaflet';

import "ag-grid-community/styles/ag-theme-quartz.css";
import 'leaflet/dist/leaflet.css';
import './App.css';

// Fix leaflet default markers
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

ModuleRegistry.registerModules([AllCommunityModule]);

function App() {
  const [allData, setAllData] = useState([]);
  const [filteredData, setFilteredData] = useState([]);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedBorough, setSelectedBorough] = useState('All');
  const [selectedPostcode, setSelectedPostcode] = useState('All');
  const [selectedLeadType, setSelectedLeadType] = useState('All');
  const [selectedPriority, setSelectedPriority] = useState('All');
  const [selectedBusiness, setSelectedBusiness] = useState(null);
  const [businessDetailOpen, setBusinessDetailOpen] = useState(false);
  const [searchSuggestions, setSearchSuggestions] = useState([]);
  const [contactDialogOpen, setContactDialogOpen] = useState(false);
  const [contactingBusiness, setContactingBusiness] = useState(null);
  const [contactNotes, setContactNotes] = useState('');

  const COLORS = {
    HIGH: '#ff5252',
    MEDIUM: '#ffc107',
    LOW: '#4caf50'
  };

  const columnDefs = [
    { 
      headerName: "Business Name", 
      field: "Business Name", 
      sortable: true, 
      filter: true, 
      resizable: true,
      flex: 1,
      minWidth: 200,
      cellRenderer: params => (
        <Button
          variant="text"
          onClick={() => {
            setSelectedBusiness(params.data);
            setBusinessDetailOpen(true);
          }}
          sx={{ 
            color: '#1976d2', 
            fontWeight: 'bold',
            textTransform: 'none',
            justifyContent: 'flex-start',
            width: '100%'
          }}
        >
          {params.value}
        </Button>
      )
    },
    { 
      headerName: "Priority", 
      field: "Priority", 
      sortable: true, 
      filter: true, 
      resizable: true,
      width: 120,
      cellRenderer: params => (
        <Chip 
          label={params.value} 
          size="small"
          style={{ 
            backgroundColor: COLORS[params.value], 
            color: params.value === 'MEDIUM' ? 'black' : 'white',
            fontWeight: 'bold'
          }}
        />
      )
    },
    { headerName: "Lead Type", field: "Lead Type", sortable: true, filter: true, resizable: true, width: 120 },
    { headerName: "Borough", field: "Borough", sortable: true, filter: true, resizable: true, width: 120 },
    { headerName: "Postcode", field: "Postcode", sortable: true, filter: true, resizable: true, width: 120 },
    { headerName: "Address", field: "Address", sortable: true, filter: true, resizable: true, flex: 1, minWidth: 250 },
    { headerName: "Phone", field: "Phone", sortable: true, filter: true, resizable: true, width: 150 },
    { 
      headerName: "Website", 
      field: "Website", 
      sortable: true, 
      filter: true, 
      resizable: true,
      width: 100,
      cellRenderer: params => (
        params.value ? (
          <Button 
            variant="outlined" 
            size="small" 
            href={params.value} 
            target="_blank" 
            rel="noopener noreferrer"
          >
            Visit
          </Button>
        ) : null
      )
    },
    { 
      headerName: "Contact Status", 
      field: "Contacted", 
      sortable: true, 
      filter: true, 
      resizable: true,
      width: 130,
      cellRenderer: params => (
        <Button
          variant={params.value ? "contained" : "outlined"}
          size="small"
          color={params.value ? "success" : "primary"}
          onClick={() => {
            setContactingBusiness(params.data);
            setContactNotes(params.data['Contact_Notes'] || '');
            setContactDialogOpen(true);
          }}
          sx={{ 
            textTransform: 'none',
            fontSize: '0.75rem',
            minWidth: '100px'
          }}
          title={params.data['Contact_Date'] ? `Contacted on ${params.data['Contact_Date']}` : 'Not contacted yet'}
        >
          {params.value ? '✅ Contacted' : '📞 Contact'}
        </Button>
      )
    },
  ];

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Use environment-specific API URL
        const apiUrl = __ENVIRONMENT__ === 'production' ? __PRODUCTION_BACKEND_URL__ : __BACKEND_URL__;
        console.log('Environment:', __ENVIRONMENT__);
        console.log('Backend URL:', __BACKEND_URL__);
        console.log('Production Backend URL:', __PRODUCTION_BACKEND_URL__);
        console.log('Using API URL:', apiUrl);
        const response = await axios.get(`${apiUrl}/api/businesses`);
        setAllData(response.data);
        setFilteredData(response.data);
        // Initialize search suggestions
        setSearchSuggestions(response.data.map(business => ({
          label: business['Business Name'],
          data: business
        })));
      } catch (err) {
        console.error("Error fetching data:", err);
        setError("Failed to connect to the backend. Please ensure the backend server is running.");
      }
    };
    fetchData();
  }, []);

  useEffect(() => {
    let filtered = allData;

    if (searchTerm) {
      filtered = filtered.filter(business => 
        business['Business Name']?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        business['Address']?.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }

    if (selectedBorough !== 'All') {
      filtered = filtered.filter(business => business.Borough === selectedBorough);
    }

    if (selectedPostcode !== 'All') {
      filtered = filtered.filter(business => business.Postcode === selectedPostcode);
    }

    if (selectedLeadType !== 'All') {
      filtered = filtered.filter(business => business['Lead Type'] === selectedLeadType);
    }

    if (selectedPriority !== 'All') {
      filtered = filtered.filter(business => business.Priority === selectedPriority);
    }

    setFilteredData(filtered);
  }, [allData, searchTerm, selectedBorough, selectedPostcode, selectedLeadType, selectedPriority]);

  const getMetrics = () => {
    const total = filteredData.length;
    const highPriority = filteredData.filter(b => b.Priority === 'HIGH').length;
    const mediumPriority = filteredData.filter(b => b.Priority === 'MEDIUM').length;
    const lowPriority = filteredData.filter(b => b.Priority === 'LOW').length;
    const withPhone = filteredData.filter(b => b.Phone).length;
    const withWebsite = filteredData.filter(b => b.Website).length;
    
    return { total, highPriority, mediumPriority, lowPriority, withPhone, withWebsite };
  };

  const getChartData = () => {
    const priorityData = [
      { name: 'High Priority', value: filteredData.filter(b => b.Priority === 'HIGH').length, color: COLORS.HIGH },
      { name: 'Medium Priority', value: filteredData.filter(b => b.Priority === 'MEDIUM').length, color: COLORS.MEDIUM },
      { name: 'Low Priority', value: filteredData.filter(b => b.Priority === 'LOW').length, color: COLORS.LOW }
    ];

    const boroughData = [...new Set(filteredData.map(b => b.Borough))].map(borough => ({
      name: borough,
      count: filteredData.filter(b => b.Borough === borough).length
    }));

    return { priorityData, boroughData };
  };

  const getUniqueValues = (field) => {
    return [...new Set(allData.map(item => item[field]))].filter(Boolean).sort();
  };

  const getFilteredPostcodes = () => {
    if (selectedBorough === 'All') {
      return getUniqueValues('Postcode');
    }
    // Filter postcodes by selected borough
    const boroughBusinesses = allData.filter(item => item.Borough === selectedBorough);
    return [...new Set(boroughBusinesses.map(item => item.Postcode))].filter(Boolean).sort();
  };

  const clearFilters = () => {
    setSearchTerm('');
    setSelectedBorough('All');
    setSelectedPostcode('All');
    setSelectedLeadType('All');
    setSelectedPriority('All');
  };

  const handleBusinessSelect = (event, newValue) => {
    if (newValue) {
      setSelectedBusiness(newValue.data);
      setBusinessDetailOpen(true);
    }
  };

  const handleContactUpdate = async (contacted) => {
    if (!contactingBusiness) return;
    
    try {
      const apiUrl = __ENVIRONMENT__ === 'production' ? __PRODUCTION_BACKEND_URL__ : __BACKEND_URL__;
      
      const businessName = encodeURIComponent(contactingBusiness['Business Name']);
      console.log('Updating contact for:', contactingBusiness['Business Name']);
      
      await axios.put(`${apiUrl}/api/businesses/${businessName}/contact`, {
        contacted: contacted,
        contact_notes: contactNotes.trim() || null
      });
      
      console.log('✅ Contact status updated successfully');
      
      // Refresh data
      console.log('Refreshing business data...');
      const response = await axios.get(`${apiUrl}/api/businesses`);
      
      // Debug: Check if the updated business is in the response
      const updatedBusiness = response.data.find(b => b['Business Name'] === contactingBusiness['Business Name']);
      console.log('Updated business data:', updatedBusiness);
      console.log('Contact status:', updatedBusiness?.Contacted);
      console.log('Contact notes:', updatedBusiness?.Contact_Notes);
      
      setAllData(response.data);
      setFilteredData(response.data);
      
      console.log('✅ Data refreshed, closing dialog');
      setContactDialogOpen(false);
      setContactingBusiness(null);
      setContactNotes('');
      
    } catch (err) {
      console.error("❌ Error updating contact status:", err);
      console.error("Error details:", err.response?.data || err.message);
      alert(`Failed to update contact status: ${err.response?.data?.detail || err.message}`);
    }
  };

  // Get default map center (London)
  const mapCenter = selectedBusiness?.Latitude && selectedBusiness?.Longitude 
    ? [parseFloat(selectedBusiness.Latitude), parseFloat(selectedBusiness.Longitude)]
    : [51.5074, -0.1278];

  const metrics = getMetrics();
  const chartData = getChartData();

  if (error) {
    return (
      <Container maxWidth="lg" sx={{ mt: 4 }}>
        <Paper elevation={3} sx={{ p: 3, textAlign: 'center', color: 'error.main' }}>
          <Typography variant="h6">{error}</Typography>
        </Paper>
      </Container>
    );
  }

  return (
    <Box sx={{ flexGrow: 1, bgcolor: '#f5f7fa', minHeight: '100vh' }}>
      <AppBar position="static" elevation={0} sx={{ bgcolor: '#1976d2' }}>
        <Toolbar>
          <Typography variant="h5" component="div" sx={{ flexGrow: 1, fontWeight: 'bold' }}>
            🌿 Evergreen Business Leads Dashboard
          </Typography>
        </Toolbar>
      </AppBar>

      <Container maxWidth="xl" sx={{ py: 3 }}>
        {/* Business Search Section */}
        <Card elevation={2} sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>Find Specific Business</Typography>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12, md: 6 }}>
                <Autocomplete
                  options={searchSuggestions}
                  getOptionLabel={(option) => option.label}
                  onChange={handleBusinessSelect}
                  renderInput={(params) => (
                    <TextField
                      {...params}
                      label="Search for a specific business..."
                      variant="outlined"
                      fullWidth
                    />
                  )}
                  renderOption={(props, option) => (
                    <Box component="li" {...props}>
                      <Box sx={{ display: 'flex', alignItems: 'center', width: '100%' }}>
                        <Avatar 
                          sx={{ 
                            bgcolor: COLORS[option.data.Priority], 
                            width: 24, 
                            height: 24, 
                            mr: 2,
                            fontSize: '0.75rem'
                          }}
                        >
                          {option.data.Priority[0]}
                        </Avatar>
                        <Box>
                          <Typography variant="body1" sx={{ fontWeight: 'bold' }}>
                            {option.data['Business Name']}
                          </Typography>
                          <Typography variant="body2" color="text.secondary">
                            {option.data.Address} • {option.data['Lead Type']}
                          </Typography>
                        </Box>
                      </Box>
                    </Box>
                  )}
                />
              </Grid>
              <Grid size={{ xs: 12, md: 6 }}>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
                  💡 Start typing to see suggestions, then click on any business to view details and location on map.
                </Typography>
              </Grid>
            </Grid>
          </CardContent>
        </Card>

        {/* Priority Calculation Guide */}
        <Card elevation={2} sx={{ mb: 3, bgcolor: '#f8f9fa' }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              📊 How Priority Levels Are Calculated
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              Business priorities are automatically assigned based on keywords in the business name and cuisine type to identify the most valuable prospects for each product category.
            </Typography>
            <Grid container spacing={3}>
              <Grid size={{ xs: 12, md: 6 }}>
                <Paper elevation={1} sx={{ p: 2, bgcolor: 'white' }}>
                  <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
                    🌶️ Spice Products
                  </Typography>
                  <Box sx={{ mb: 1 }}>
                    <Chip label="HIGH" size="small" sx={{ bgcolor: COLORS.HIGH, color: 'white', mr: 1, mb: 1 }} />
                    <Typography variant="body2" component="span">
                      Indian, Curry, Tandoori, Bengali, Pakistani, Thai, Chinese, Asian, Kebab, Halal restaurants
                    </Typography>
                  </Box>
                  <Box sx={{ mb: 1 }}>
                    <Chip label="MEDIUM" size="small" sx={{ bgcolor: COLORS.MEDIUM, color: 'black', mr: 1, mb: 1 }} />
                    <Typography variant="body2" component="span">
                      General restaurants, kitchens, grills, takeaways, cafes
                    </Typography>
                  </Box>
                  <Box>
                    <Chip label="LOW" size="small" sx={{ bgcolor: COLORS.LOW, color: 'white', mr: 1, mb: 1 }} />
                    <Typography variant="body2" component="span">
                      All other business types
                    </Typography>
                  </Box>
                </Paper>
              </Grid>
              <Grid size={{ xs: 12, md: 6 }}>
                <Paper elevation={1} sx={{ p: 2, bgcolor: 'white' }}>
                  <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
                    🍟 Cooking Oil Products
                  </Typography>
                  <Box sx={{ mb: 1 }}>
                    <Chip label="HIGH" size="small" sx={{ bgcolor: COLORS.HIGH, color: 'white', mr: 1, mb: 1 }} />
                    <Typography variant="body2" component="span">
                      Fish & Chips, Fried Chicken, Kebab, Fast Food, Takeaway, Burger, Pizza joints
                    </Typography>
                  </Box>
                  <Box sx={{ mb: 1 }}>
                    <Chip label="MEDIUM" size="small" sx={{ bgcolor: COLORS.MEDIUM, color: 'black', mr: 1, mb: 1 }} />
                    <Typography variant="body2" component="span">
                      Restaurants, cafes, pubs, diners, grills
                    </Typography>
                  </Box>
                  <Box>
                    <Chip label="LOW" size="small" sx={{ bgcolor: COLORS.LOW, color: 'white', mr: 1, mb: 1 }} />
                    <Typography variant="body2" component="span">
                      All other business types
                    </Typography>
                  </Box>
                </Paper>
              </Grid>
            </Grid>
            <Typography variant="caption" color="text.secondary" sx={{ mt: 2, display: 'block' }}>
              💡 Priorities are determined by analyzing business names, cuisine types, and amenity categories for optimal lead qualification.
            </Typography>
          </CardContent>
        </Card>

        {/* Key Metrics */}
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid size={{ xs: 6, sm: 4, md: 2 }}>
            <Card elevation={2}>
              <CardContent sx={{ textAlign: 'center', py: 2 }}>
                <Typography variant="h4" color="primary" fontWeight="bold">{metrics.total}</Typography>
                <Typography variant="body2" color="text.secondary">Total Businesses</Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid size={{ xs: 6, sm: 4, md: 2 }}>
            <Card elevation={2}>
              <CardContent sx={{ textAlign: 'center', py: 2 }}>
                <Typography variant="h4" sx={{ color: COLORS.HIGH, fontWeight: 'bold' }}>{metrics.highPriority}</Typography>
                <Typography variant="body2" color="text.secondary">High Priority</Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid size={{ xs: 6, sm: 4, md: 2 }}>
            <Card elevation={2}>
              <CardContent sx={{ textAlign: 'center', py: 2 }}>
                <Typography variant="h4" sx={{ color: COLORS.MEDIUM, fontWeight: 'bold' }}>{metrics.mediumPriority}</Typography>
                <Typography variant="body2" color="text.secondary">Medium Priority</Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid size={{ xs: 6, sm: 4, md: 2 }}>
            <Card elevation={2}>
              <CardContent sx={{ textAlign: 'center', py: 2 }}>
                <Typography variant="h4" sx={{ color: COLORS.LOW, fontWeight: 'bold' }}>{metrics.lowPriority}</Typography>
                <Typography variant="body2" color="text.secondary">Low Priority</Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid size={{ xs: 6, sm: 4, md: 2 }}>
            <Card elevation={2}>
              <CardContent sx={{ textAlign: 'center', py: 2 }}>
                <Typography variant="h4" color="success.main" fontWeight="bold">{metrics.withPhone}</Typography>
                <Typography variant="body2" color="text.secondary">With Phone</Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid size={{ xs: 6, sm: 4, md: 2 }}>
            <Card elevation={2}>
              <CardContent sx={{ textAlign: 'center', py: 2 }}>
                <Typography variant="h4" color="info.main" fontWeight="bold">{metrics.withWebsite}</Typography>
                <Typography variant="body2" color="text.secondary">With Website</Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>

        {/* Charts */}
        <Grid container spacing={3} sx={{ mb: 3 }}>
          <Grid size={{ xs: 12, lg: 6 }}>
            <Card elevation={2}>
              <CardContent>
                <Typography variant="h6" gutterBottom>Priority Distribution</Typography>
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie
                      data={chartData.priorityData}
                      cx="50%"
                      cy="50%"
                      outerRadius={100}
                      fill="#8884d8"
                      dataKey="value"
                      label={({ name, value }) => `${name}: ${value}`}
                    >
                      {chartData.priorityData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </Grid>
          <Grid size={{ xs: 12, lg: 6 }}>
            <Card elevation={2}>
              <CardContent>
                <Typography variant="h6" gutterBottom>Businesses by Borough</Typography>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={chartData.boroughData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey="count" fill="#1976d2" />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </Grid>
        </Grid>

        {/* Filters */}
        <Card elevation={2} sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>Filters & Search</Typography>
            <Grid container spacing={2} alignItems="center">
              <Grid size={{ xs: 12, lg: 3 }}>
                <TextField
                  fullWidth
                  label="Search Business or Address"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  variant="outlined"
                  size="small"
                />
              </Grid>
              <Grid size={{ xs: 6, sm: 3, lg: 2 }}>
                <FormControl fullWidth size="small">
                  <InputLabel>Borough</InputLabel>
                  <Select
                    value={selectedBorough}
                    onChange={(e) => {
                      setSelectedBorough(e.target.value);
                      setSelectedPostcode('All'); // Reset postcode when borough changes
                    }}
                    label="Borough"
                  >
                    <MenuItem value="All">All</MenuItem>
                    {getUniqueValues('Borough').map(borough => (
                      <MenuItem key={borough} value={borough}>{borough}</MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
              <Grid size={{ xs: 6, sm: 3, lg: 2 }}>
                <FormControl fullWidth size="small">
                  <InputLabel>Postcode</InputLabel>
                  <Select
                    value={selectedPostcode}
                    onChange={(e) => setSelectedPostcode(e.target.value)}
                    label="Postcode"
                  >
                    <MenuItem value="All">All</MenuItem>
                    {getFilteredPostcodes().map(postcode => (
                      <MenuItem key={postcode} value={postcode}>{postcode}</MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
              <Grid size={{ xs: 6, sm: 3, lg: 2 }}>
                <FormControl fullWidth size="small">
                  <InputLabel>Lead Type</InputLabel>
                  <Select
                    value={selectedLeadType}
                    onChange={(e) => setSelectedLeadType(e.target.value)}
                    label="Lead Type"
                  >
                    <MenuItem value="All">All</MenuItem>
                    {getUniqueValues('Lead Type').map(type => (
                      <MenuItem key={type} value={type}>{type}</MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
              <Grid size={{ xs: 6, sm: 3, lg: 2 }}>
                <FormControl fullWidth size="small">
                  <InputLabel>Priority</InputLabel>
                  <Select
                    value={selectedPriority}
                    onChange={(e) => setSelectedPriority(e.target.value)}
                    label="Priority"
                  >
                    <MenuItem value="All">All</MenuItem>
                    <MenuItem value="HIGH">High</MenuItem>
                    <MenuItem value="MEDIUM">Medium</MenuItem>
                    <MenuItem value="LOW">Low</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid size={{ xs: 12, sm: 3, lg: 1 }}>
                <Button 
                  variant="outlined" 
                  onClick={clearFilters}
                  size="small"
                  fullWidth
                >
                  Clear
                </Button>
              </Grid>
            </Grid>
          </CardContent>
        </Card>

        {/* Data Grid */}
        <Card elevation={2}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Business Directory ({filteredData.length} results)
            </Typography>
            <div className="ag-theme-quartz" style={{ height: '70vh', width: '100%' }}>
              <AgGridReact
                key={`grid-${filteredData.length}-${JSON.stringify(filteredData.slice(0,1))}`}
                rowData={filteredData}
                columnDefs={columnDefs}
                defaultColDef={{
                  sortable: true,
                  filter: true,
                  resizable: true
                }}
                pagination={true}
                paginationPageSize={20}
                paginationPageSizeSelector={[20, 50, 100]}
                rowSelection={{
                  mode: 'multiRow',
                  enableClickSelection: false
                }}
                animateRows={true}
              />
      </div>
          </CardContent>
        </Card>
      </Container>

      {/* Business Detail Dialog */}
      <Dialog 
        open={businessDetailOpen} 
        onClose={() => setBusinessDetailOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle sx={{ pb: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Avatar sx={{ bgcolor: COLORS[selectedBusiness?.Priority] }}>
              {selectedBusiness?.Priority?.[0]}
            </Avatar>
            <Box>
              <Typography variant="h6">{selectedBusiness?.['Business Name']}</Typography>
              <Chip 
                label={`${selectedBusiness?.['Lead Type']} • ${selectedBusiness?.Priority} Priority`}
                size="small"
                sx={{ mt: 0.5 }}
              />
            </Box>
          </Box>
        </DialogTitle>
        <DialogContent>
          <Grid container spacing={3}>
            <Grid size={{ xs: 12, md: 6 }}>
              <Typography variant="subtitle1" fontWeight="bold" gutterBottom>Contact Information</Typography>
              <Typography variant="body2" paragraph>
                <strong>Address:</strong> {selectedBusiness?.Address}
              </Typography>
              <Typography variant="body2" paragraph>
                <strong>Borough:</strong> {selectedBusiness?.Borough}
              </Typography>
              <Typography variant="body2" paragraph>
                <strong>Postcode:</strong> {selectedBusiness?.Postcode}
              </Typography>
              {selectedBusiness?.Phone && (
                <Typography variant="body2" paragraph>
                  <strong>Phone:</strong> {selectedBusiness.Phone}
                </Typography>
              )}
              {selectedBusiness?.Website && (
                <Typography variant="body2" paragraph>
                  <strong>Website:</strong>{' '}
                  <Button 
                    variant="text" 
                    href={selectedBusiness.Website} 
                    target="_blank"
                    size="small"
                  >
                    Visit Website
                  </Button>
                </Typography>
              )}
            </Grid>
            <Grid size={{ xs: 12, md: 6 }}>
              <Typography variant="subtitle1" fontWeight="bold" gutterBottom>Location</Typography>
              <Box sx={{ height: 300, width: '100%', bgcolor: '#f5f5f5', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                {selectedBusiness?.Latitude && selectedBusiness?.Longitude ? (
                  <MapContainer 
                    center={mapCenter} 
                    zoom={15} 
                    style={{ height: '100%', width: '100%' }}
                  >
                    <TileLayer
                      url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                      attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                    />
                    <Marker position={mapCenter}>
                      <Popup>
                        <strong>{selectedBusiness['Business Name']}</strong><br />
                        {selectedBusiness.Address}
                      </Popup>
                    </Marker>
                  </MapContainer>
                ) : (
                  <Typography variant="body2" color="text.secondary">
                    📍 Location coordinates not available
                  </Typography>
                )}
              </Box>
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setBusinessDetailOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>

      {/* Contact Update Dialog */}
      <Dialog 
        open={contactDialogOpen} 
        onClose={() => setContactDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>
          Update Contact Status - {contactingBusiness?.['Business Name']}
        </DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
            <Typography variant="body2" color="text.secondary">
              <strong>Business:</strong> {contactingBusiness?.['Business Name']}<br/>
              <strong>Address:</strong> {contactingBusiness?.Address}<br/>
              <strong>Phone:</strong> {contactingBusiness?.Phone || 'Not available'}
            </Typography>
            
            <Divider />
            
            <TextField
              label="Contact Notes"
              multiline
              rows={4}
              value={contactNotes}
              onChange={(e) => setContactNotes(e.target.value)}
              placeholder="Enter details about your conversation, follow-up needed, etc..."
              variant="outlined"
              fullWidth
            />
            
            {contactingBusiness?.['Contact_Date'] && (
              <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic' }}>
                Previously contacted on: {contactingBusiness['Contact_Date']}
              </Typography>
            )}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setContactDialogOpen(false)}>Cancel</Button>
          <Button 
            onClick={() => handleContactUpdate(false)}
            color="warning"
            variant="outlined"
          >
            Mark as Not Contacted
          </Button>
          <Button 
            onClick={() => handleContactUpdate(true)}
            color="success"
            variant="contained"
          >
            Mark as Contacted
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

export default App;
