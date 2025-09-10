import { useState } from 'react'
import {
  Container,
  Paper,
  TextField,
  Button,
  Typography,
  Box,
  Alert,
  Card,
  CardContent,
  AppBar,
  Toolbar
} from '@mui/material'
import { useAuth } from '../contexts/AuthContext'

export default function Auth() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [isSignUp, setIsSignUp] = useState(false)
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const { signIn, signUp } = useAuth()

  const handleSubmit = async (e) => {
    e.preventDefault()
    
    if (!email || !password) {
      setError('Email and password are required')
      return
    }

    setLoading(true)
    setError('')
    setMessage('')

    try {
      const { error } = isSignUp 
        ? await signUp(email, password)
        : await signIn(email, password)

      if (error) {
        console.error('Auth error:', error)
        setError(error.message)
      } else if (isSignUp) {
        setMessage('Check your email for verification link')
      }
    } catch (err) {
      setError('An unexpected error occurred')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Box sx={{ flexGrow: 1, bgcolor: '#f5f7fa', minHeight: '100vh' }}>
      <AppBar position="static" elevation={0} sx={{ bgcolor: '#1976d2' }}>
        <Toolbar>
          <Typography variant="h5" component="div" sx={{ flexGrow: 1, fontWeight: 'bold' }}>
            Evergreen Business Leads Dashboard
          </Typography>
        </Toolbar>
      </AppBar>

      <Box
        sx={{
          width: '100%',
          minHeight: { xs: 'calc(100dvh - 56px)', sm: 'calc(100dvh - 64px)' },
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          px: 2,
          py: { xs: 4, sm: 6 },
          overflowY: 'auto',
        }}
      >
        <Card
          elevation={3}
          sx={{
            width: '100%',
            maxWidth: { xs: 360, sm: 420 },
            mx: 'auto',
            // marginLeft: '600px'
          }}
        >
          <CardContent sx={{ p: { xs: 2, sm: 4 } }}>
            <Typography variant="h4" align="center" gutterBottom sx={{ fontSize: { xs: '1.5rem', sm: '2rem' } }}>
              {isSignUp ? 'Sign Up' : 'Sign In'}
            </Typography>
            
            <Typography variant="body2" align="center" color="text.secondary" paragraph sx={{ mt: 0 }}>
              {isSignUp 
                ? 'Create an account to access business leads'
                : 'Sign in to access your business leads dashboard'
              }
            </Typography>

            <Box component="form" onSubmit={handleSubmit} sx={{ mt: { xs: 2, sm: 3 } }}>
              <TextField
                fullWidth
                label="Email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                margin="normal"
                required
                autoComplete="email"
              />
              
              <TextField
                fullWidth
                label="Password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                margin="normal"
                required
                autoComplete={isSignUp ? 'new-password' : 'current-password'}
              />

              {error && (
                <Alert severity="error" sx={{ mt: 2 }}>
                  {error}
                </Alert>
              )}

              {message && (
                <Alert severity="success" sx={{ mt: 2 }}>
                  {message}
                </Alert>
              )}

              <Button
                type="submit"
                fullWidth
                variant="contained"
                disabled={loading}
                sx={{ mt: 3, mb: 2, py: { xs: 1.25, sm: 1.5 } }}
              >
                {loading ? 'Loading...' : (isSignUp ? 'Sign Up' : 'Sign In')}
              </Button>

              <Button
                type="button"
                fullWidth
                variant="text"
                onClick={() => setIsSignUp(!isSignUp)}
                sx={{ mt: 1 }}
              >
                {isSignUp ? 'Already have an account? Sign In' : 'Need an account? Sign Up'}
              </Button>
            </Box>
          </CardContent>
        </Card>
      </Box>
    </Box>
  )
}
