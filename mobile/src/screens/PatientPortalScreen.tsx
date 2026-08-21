import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
  SafeAreaView,
  Alert,
} from 'react-native';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';

export const PatientPortalScreen: React.FC = () => {
  const { user, logout } = useAuth();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [paying, setPaying] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const fetchPortalData = async () => {
    try {
      const res = await api.get('/patient-portal/my-care');
      setData(res.data);
    } catch (e) {
      console.error('Error fetching patient portal:', e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchPortalData();
  }, []);

  const onRefresh = () => {
    setRefreshing(true);
    fetchPortalData();
  };

  const handleSimulateUpi = async () => {
    if (!data?.invoice?.invoice_number) return;
    setPaying(true);
    try {
      await api.post('/billing/online/webhook', {
        invoice_number: data.invoice.invoice_number,
        amount: data.invoice.balance_amount,
        transaction_reference: `UPI-MOB-${Date.now()}`,
      });
      Alert.alert('Payment Successful', 'UPI payment settled. Discharge / Ambulance transport clearance triggered!');
      fetchPortalData();
    } catch (err: any) {
      Alert.alert('Payment Error', err.response?.data?.detail || 'Payment simulation failed.');
    } finally {
      setPaying(false);
    }
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <ActivityIndicator size="large" color="#10b981" style={{ marginTop: 60 }} />
      </SafeAreaView>
    );
  }

  const patient = data?.patient;
  const invoice = data?.invoice;
  const dischargePackage = data?.discharge_package;

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.greeting}>Patient Care Portal</Text>
          <Text style={styles.patientName}>{patient?.full_name || user?.name}</Text>
        </View>
        <TouchableOpacity style={styles.logoutBtn} onPress={logout}>
          <Text style={styles.logoutText}>Sign Out</Text>
        </TouchableOpacity>
      </View>

      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#34d399" />}
      >
        {/* Recovery Plan Card */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>📋 Recovery & Care Instructions</Text>
          <Text style={styles.careSummary}>
            {dischargePackage?.patient_summary || 'Your attending medical team has stabilized your vital parameters. Please follow prescribed medications and dietary guidance.'}
          </Text>
        </View>

        {/* Itemized Billing & UPI Pay Card */}
        {invoice && (
          <View style={styles.card}>
            <View style={styles.billHeader}>
              <Text style={styles.cardTitle}>💳 Hospital Billing</Text>
              <View style={[styles.payBadge, invoice.payment_status === 'paid_online' ? styles.badgePaid : styles.badgePending]}>
                <Text style={styles.payBadgeText}>{invoice.payment_status.toUpperCase()}</Text>
              </View>
            </View>

            <View style={styles.billRow}>
              <Text style={styles.billLabel}>Invoice Number:</Text>
              <Text style={styles.billValue}>#{invoice.invoice_number}</Text>
            </View>
            <View style={styles.billRow}>
              <Text style={styles.billLabel}>Total Amount:</Text>
              <Text style={styles.billValue}>₹{Number(invoice.total_amount).toFixed(2)}</Text>
            </View>
            <View style={styles.billRow}>
              <Text style={styles.billLabel}>Outstanding Balance:</Text>
              <Text style={styles.billBalance}>₹{Number(invoice.balance_amount).toFixed(2)}</Text>
            </View>

            {invoice.payment_status === 'pending' && (
              <TouchableOpacity
                style={styles.payBtn}
                onPress={handleSimulateUpi}
                disabled={paying}
              >
                {paying ? (
                  <ActivityIndicator color="#ffffff" />
                ) : (
                  <Text style={styles.payBtnText}>⚡ Simulate Instant UPI Payment</Text>
                )}
              </TouchableOpacity>
            )}
          </View>
        )}
      </ScrollView>
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
    fontSize: 12,
    color: '#34d399',
    fontWeight: 'bold',
    textTransform: 'uppercase',
  },
  patientName: {
    fontSize: 17,
    fontWeight: 'bold',
    color: '#ffffff',
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
  scrollContent: {
    padding: 16,
    gap: 14,
  },
  card: {
    backgroundColor: '#0f172a',
    borderRadius: 14,
    padding: 16,
    borderWidth: 1,
    borderColor: '#1e293b',
  },
  cardTitle: {
    fontSize: 15,
    fontWeight: 'bold',
    color: '#ffffff',
    marginBottom: 8,
  },
  careSummary: {
    fontSize: 13,
    color: '#cbd5e1',
    lineHeight: 20,
  },
  billHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  payBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  badgePaid: {
    backgroundColor: '#064e3b',
  },
  badgePending: {
    backgroundColor: '#78350f',
  },
  payBadgeText: {
    color: '#ffffff',
    fontSize: 10,
    fontWeight: 'bold',
  },
  billRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 4,
  },
  billLabel: {
    fontSize: 13,
    color: '#94a3b8',
  },
  billValue: {
    fontSize: 13,
    color: '#f1f5f9',
    fontWeight: '600',
  },
  billBalance: {
    fontSize: 14,
    color: '#34d399',
    fontWeight: 'bold',
  },
  payBtn: {
    backgroundColor: '#10b981',
    padding: 12,
    borderRadius: 10,
    alignItems: 'center',
    marginTop: 14,
  },
  payBtnText: {
    color: '#ffffff',
    fontWeight: 'bold',
    fontSize: 13,
  },
});
