import { useState, useEffect } from 'react'
import { supabase } from '../lib/supabase'

export function useBusinessData() {
  const [allData, setAllData] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchBusinesses = async () => {
    try {
      setLoading(true)
      const { data, error } = await supabase
        .from('businesses')
        .select('*')
        .order('business_name')

      if (error) throw error

      //transform to match existing component expectations
      const transformedData = data.map(business => ({
        'Business Name': business.business_name,
        'Priority': business.priority,
        'Lead Type': business.lead_type,
        'Borough': business.borough,
        'Postcode': business.postcode,
        'Address': business.address,
        'Phone': business.phone,
        'Website': business.website,
        'Cuisine Type': business.cuisine_type,
        'Latitude': business.latitude,
        'Longitude': business.longitude,
        'Source': business.source,
        'Contacted': business.contacted,
        'Contact_Date': business.contact_date,
        'Contact_Notes': business.contact_notes
      }))

      setAllData(transformedData)
      setError(null)
    } catch (err) {
      setError(err.message)
      setAllData([])
    } finally {
      setLoading(false)
    }
  }

  const updateContactStatus = async (businessName, contacted, contactNotes) => {
    try {
      const { error } = await supabase
        .from('businesses')
        .update({
          contacted,
          contact_date: contacted ? new Date().toISOString().split('T')[0] : null,
          contact_notes: contactNotes || null,
          updated_at: new Date().toISOString()
        })
        .eq('business_name', businessName)

      if (error) throw error

      //refresh data after update
      await fetchBusinesses()
      return true
    } catch (err) {
      console.error('Error updating contact status:', err)
      throw err
    }
  }

  useEffect(() => {
    fetchBusinesses()
  }, [])

  return {
    allData,
    loading,
    error,
    refetch: fetchBusinesses,
    updateContactStatus
  }
}