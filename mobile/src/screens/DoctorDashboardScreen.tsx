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
} from 'react-native';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';

export const DoctorDashboardScreen: React.FC<{ navigation: any }> = ({ navigation }) => {
  const { user, logout } = useAuth();
  const [patients, setPatients] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchPatients = async () => {
    try {
      const res = await api.get('/patients');
      setPatients(res.data.items || res.data || []);
    } catch (e) {
      console.error('Error fetching patients:', e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchPatients();
  }, []);

  const onRefresh = () => {
    setRefreshing(true);
    fetchPatients();
  };

  const renderPatientCard = ({ item }: { item: any }) => {
    return (
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <View>
            <Text style={styles.patientName}>{item.full_name || `${item.first_name} ${item.last_name}`}</Text>
            <Text style={styles.patientCode}>{item.patient_code} • Age {item.age || 48} • {item.gender}</Text>
          </View>
          <View style={[styles.statusBadge, item.active_admission_status === 'transfer_pending' ? styles.badgeTransfer : styles.badgeAdmitted]}>
            <Text style={styles.statusText}>
              {(item.active_admission_status || 'ADMITTED').toUpperCase()}
            </Text>
          </View>
        </View>

        <View style={styles.cardDetails}>
          <Text style={styles.detailText}>
            🛏️ Bed: <Text style={styles.detailBold}>{item.bed_number || 'GM-12'} ({item.ward || 'General Medicine'})</Text>
          </Text>
          <Text style={styles.detailText}>
            🩺 Diagnosis: <Text style={styles.detailBold}>{item.primary_diagnosis || 'Community Acquired Pneumonia'}</Text>
          </Text>
        </View>

        <View style={styles.cardActions}>
          <TouchableOpacity
            style={styles.actionBtnPrimary}
            onPress={() => navigation.navigate('Transfers')}
          >
            <Text style={styles.actionBtnText}>Transfer Triage</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  };

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.greeting}>Welcome, {user?.name}</Text>
          <Text style={styles.roleLabel}>Role: {user?.role.toUpperCase()}</Text>
        </View>
        <TouchableOpacity style={styles.logoutBtn} onPress={logout}>
          <Text style={styles.logoutText}>Sign Out</Text>
        </TouchableOpacity>
      </View>

      {/* Patient Queue */}
      <View style={styles.content}>
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>Active Ward Inpatients</Text>
          <Text style={styles.patientCount}>{patients.length} Patients</Text>
        </View>

        {loading ? (
          <ActivityIndicator size="large" color="#0284c7" style={{ marginTop: 40 }} />
        ) : (
          <FlatList
            data={patients}
            keyExtractor={(item) => String(item.id)}
            renderItem={renderPatientCard}
            refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#38bdf8" />}
            contentContainerStyle={styles.listContent}
          />
        )}
      </View>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#020617',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#1e293b',
    backgroundColor: '#0f172a',
  },
  greeting: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#ffffff',
  },
  roleLabel: {
    fontSize: 11,
    color: '#38bdf8',
    fontWeight: '600',
    marginTop: 2,
  },
  logoutBtn: {
    backgroundColor: '#334155',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
  },
  logoutText: {
    color: '#f1f5f9',
    fontSize: 12,
    fontWeight: '600',
  },
  content: {
    flex: 1,
    padding: 16,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: 17,
    fontWeight: 'bold',
    color: '#ffffff',
  },
  patientCount: {
    fontSize: 12,
    color: '#94a3b8',
  },
  listContent: {
    gap: 12,
    paddingBottom: 20,
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
  patientCode: {
    fontSize: 12,
    color: '#64748b',
    marginTop: 2,
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  badgeAdmitted: {
    backgroundColor: '#064e3b',
  },
  badgeTransfer: {
    backgroundColor: '#7c2d12',
  },
  statusText: {
    color: '#ffffff',
    fontSize: 10,
    fontWeight: 'bold',
  },
  cardDetails: {
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#1e293b',
    gap: 4,
  },
  detailText: {
    fontSize: 12,
    color: '#94a3b8',
  },
  detailBold: {
    color: '#e2e8f0',
    fontWeight: '600',
  },
  cardActions: {
    marginTop: 12,
    flexDirection: 'row',
    justifyContent: 'flex-end',
  },
  actionBtnPrimary: {
    backgroundColor: '#0284c7',
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
  },
  actionBtnText: {
    color: '#ffffff',
    fontSize: 12,
    fontWeight: 'bold',
  },
});
