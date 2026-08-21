import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
  SafeAreaView,
  Alert,
} from 'react-native';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';

export const TransfersScreen: React.FC = () => {
  const { user } = useAuth();
  const [transfers, setTransfers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchTransfers = async () => {
    try {
      const endpoint = user?.role === 'receiving_doctor' ? '/receiving/transfers' : '/transfers';
      const res = await api.get(endpoint);
      setTransfers(res.data.items || res.data || []);
    } catch (e) {
      console.error('Error fetching transfers:', e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchTransfers();
  }, []);

  const onRefresh = () => {
    setRefreshing(true);
    fetchTransfers();
  };

  const handleAcceptTransfer = async (transferId: number) => {
    try {
      await api.post(`/transfers/${transferId}/accept`, {
        notes: 'Bed reserved via Mobile Care Suite. Patient accepted.',
      });
      Alert.alert('Transfer Accepted', 'Bed capacity reserved at destination facility.');
      fetchTransfers();
    } catch (err: any) {
      Alert.alert('Error', err.response?.data?.detail || 'Failed to accept transfer');
    }
  };

  const renderTransferCard = ({ item }: { item: any }) => {
    const isReceiving = user?.role === 'receiving_doctor';
    const hasAmbulance = item.ambulance || item.ambulance_dispatch;

    return (
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <View>
            <Text style={styles.patientName}>{item.patient_name || `Patient #${item.patient_id}`}</Text>
            <Text style={styles.transferMeta}>
              Case #{item.id} • {item.required_specialty || 'Cardiology'}
            </Text>
          </View>
          <View style={[styles.urgencyBadge, item.emergency ? styles.badgeEmergency : styles.badgeNonEmergency]}>
            <Text style={styles.urgencyText}>{item.emergency ? '🚨 EMERGENCY' : '📋 ELECTIVE'}</Text>
          </View>
        </View>

        <View style={styles.facilitySection}>
          <Text style={styles.facilityText}>
            From: <Text style={styles.bold}>{item.sending_hospital_name || 'Metro Multispeciality'}</Text>
          </Text>
          <Text style={styles.facilityText}>
            To: <Text style={styles.bold}>{item.receiving_hospital_name || 'City Heart & Neuro'}</Text>
          </Text>
          <Text style={styles.statusText}>
            Status: <Text style={styles.statusHighlight}>{item.status.toUpperCase()}</Text>
          </Text>
        </View>

        {/* Live Ambulance Banner if en route */}
        {hasAmbulance && (
          <View style={styles.ambulanceCard}>
            <Text style={styles.ambulanceTitle}>🚑 Emergency Transport En Route</Text>
            <Text style={styles.ambulanceDetails}>
              Vehicle: {hasAmbulance.vehicle_number || 'TN-DEMO-101'} • ETA: {hasAmbulance.current_eta_minutes || 8} mins
            </Text>
            <Text style={styles.ambulanceDriver}>
              Driver: {hasAmbulance.driver_name || 'Ramesh Kumar'} ({hasAmbulance.driver_phone || '+91-98765-43210'})
            </Text>
          </View>
        )}

        {/* Actions */}
        {isReceiving && item.status === 'awaiting_acceptance' && (
          <TouchableOpacity
            style={styles.acceptBtn}
            onPress={() => handleAcceptTransfer(item.id)}
          >
            <Text style={styles.acceptBtnText}>✓ Accept Transfer & Reserve Bed</Text>
          </TouchableOpacity>
        )}
      </View>
    );
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>
          {user?.role === 'receiving_doctor' ? 'Incoming Transfer Cases' : 'Inter-Hospital Transfers'}
        </Text>
      </View>

      {loading ? (
        <ActivityIndicator size="large" color="#0284c7" style={{ marginTop: 40 }} />
      ) : (
        <FlatList
          data={transfers}
          keyExtractor={(item) => String(item.id)}
          renderItem={renderTransferCard}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#38bdf8" />}
          contentContainerStyle={styles.listContent}
          ListEmptyComponent={
            <View style={styles.emptyContainer}>
              <Text style={styles.emptyText}>No active transfer cases in queue.</Text>
            </View>
          }
        />
      )}
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#020617',
  },
  header: {
    paddingHorizontal: 20,
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#1e293b',
    backgroundColor: '#0f172a',
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#ffffff',
  },
  listContent: {
    padding: 16,
    gap: 12,
  },
  card: {
    backgroundColor: '#0f172a',
    borderRadius: 14,
    padding: 16,
    borderWidth: 1,
    borderColor: '#1e293b',
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  patientName: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#ffffff',
  },
  transferMeta: {
    fontSize: 12,
    color: '#94a3b8',
    marginTop: 2,
  },
  urgencyBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  badgeEmergency: {
    backgroundColor: '#991b1b',
  },
  badgeNonEmergency: {
    backgroundColor: '#1e3a8a',
  },
  urgencyText: {
    color: '#ffffff',
    fontSize: 10,
    fontWeight: 'bold',
  },
  facilitySection: {
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#1e293b',
    gap: 4,
  },
  facilityText: {
    fontSize: 12,
    color: '#94a3b8',
  },
  bold: {
    color: '#f8fafc',
    fontWeight: '600',
  },
  statusText: {
    fontSize: 12,
    color: '#94a3b8',
    marginTop: 4,
  },
  statusHighlight: {
    color: '#38bdf8',
    fontWeight: 'bold',
  },
  ambulanceCard: {
    backgroundColor: '#022c22',
    borderColor: '#065f46',
    borderWidth: 1,
    borderRadius: 10,
    padding: 12,
    marginTop: 12,
  },
  ambulanceTitle: {
    color: '#34d399',
    fontWeight: 'bold',
    fontSize: 13,
  },
  ambulanceDetails: {
    color: '#a7f3d0',
    fontSize: 12,
    marginTop: 4,
  },
  ambulanceDriver: {
    color: '#6ee7b7',
    fontSize: 11,
    marginTop: 2,
  },
  acceptBtn: {
    backgroundColor: '#10b981',
    padding: 12,
    borderRadius: 10,
    alignItems: 'center',
    marginTop: 14,
  },
  acceptBtnText: {
    color: '#ffffff',
    fontWeight: 'bold',
    fontSize: 13,
  },
  emptyContainer: {
    padding: 40,
    alignItems: 'center',
  },
  emptyText: {
    color: '#64748b',
    fontSize: 14,
  },
});
