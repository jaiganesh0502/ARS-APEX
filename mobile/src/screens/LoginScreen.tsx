import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  SafeAreaView,
  StatusBar,
} from 'react-native';
import { useAuth } from '../context/AuthContext';

export const LoginScreen: React.FC = () => {
  const { login } = useAuth();
  const [email, setEmail] = useState('doctor@demo.local');
  const [password, setPassword] = useState('DoctorDemo123!');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLogin = async () => {
    setLoading(true);
    setError(null);
    const success = await login(email, password);
    setLoading(false);
    if (!success) {
      setError('Invalid credentials. Please verify and retry.');
    }
  };

  const setPreset = (e: string, p: string) => {
    setEmail(e);
    setPassword(p);
  };

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="light-content" backgroundColor="#020617" />
      <ScrollView contentContainerStyle={styles.scrollContent}>
        {/* Brand Header */}
        <View style={styles.header}>
          <View style={styles.logoBadge}>
            <Text style={styles.logoText}>⚡ ALTA</Text>
          </View>
          <Text style={styles.title}>Alta Hospital Care</Text>
          <Text style={styles.subtitle}>Discharge & Inter-Hospital Transfer Suite</Text>
        </View>

        {/* Login Card */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Staff & Patient Sign In</Text>

          {error && (
            <View style={styles.errorBanner}>
              <Text style={styles.errorText}>{error}</Text>
            </View>
          )}

          <View style={styles.inputGroup}>
            <Text style={styles.label}>Email Address</Text>
            <TextInput
              style={styles.input}
              value={email}
              onChangeText={setEmail}
              autoCapitalize="none"
              keyboardType="email-address"
              placeholder="name@hospital.org"
              placeholderTextColor="#64748b"
            />
          </View>

          <View style={styles.inputGroup}>
            <Text style={styles.label}>Password</Text>
            <TextInput
              style={styles.input}
              value={password}
              onChangeText={setPassword}
              secureTextEntry
              placeholder="••••••••"
              placeholderTextColor="#64748b"
            />
          </View>

          <TouchableOpacity
            style={styles.loginButton}
            onPress={handleLogin}
            disabled={loading}
          >
            {loading ? (
              <ActivityIndicator color="#ffffff" />
            ) : (
              <Text style={styles.loginButtonText}>Sign In to Portal</Text>
            )}
          </TouchableOpacity>

          {/* Persona Quick Select */}
          <Text style={styles.presetHeading}>1-TAP DEMO PRESETS</Text>

          <View style={styles.presetsGrid}>
            <TouchableOpacity
              style={styles.presetButton}
              onPress={() => setPreset('doctor@demo.local', 'DoctorDemo123!')}
            >
              <Text style={styles.presetName}>🩺 Dr. Aris Thorne</Text>
              <Text style={styles.presetRole}>Attending Doctor</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.presetButton}
              onPress={() => setPreset('receiving_doctor@demo.local', 'ReceivingDemo123!')}
            >
              <Text style={styles.presetName}>🏥 Dr. Elena Rostova</Text>
              <Text style={styles.presetRole}>Receiving Physician</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.presetButton}
              onPress={() => setPreset('superintendent@demo.local', 'SuperDemo123!')}
            >
              <Text style={styles.presetName}>⚡ Dr. Marcus Vance</Text>
              <Text style={styles.presetRole}>Superintendent</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.presetButton}
              onPress={() => setPreset('patient@demo.local', 'PatientDemo123!')}
            >
              <Text style={styles.presetName}>👤 Arun Kumar (PT-1001)</Text>
              <Text style={styles.presetRole}>Patient & Bill Pay</Text>
            </TouchableOpacity>
          </View>
        </View>

        <Text style={styles.footerText}>
          Connected to https://altaa.duckdns.org • FHIR R4 Compliant
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#020617',
  },
  scrollContent: {
    padding: 20,
    justifyContent: 'center',
    minHeight: '100%',
  },
  header: {
    alignItems: 'center',
    marginBottom: 24,
  },
  logoBadge: {
    backgroundColor: '#0284c7',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
    marginBottom: 10,
  },
  logoText: {
    color: '#ffffff',
    fontWeight: 'bold',
    fontSize: 14,
    letterSpacing: 1.5,
  },
  title: {
    fontSize: 26,
    fontWeight: 'bold',
    color: '#ffffff',
    textAlign: 'center',
  },
  subtitle: {
    fontSize: 13,
    color: '#94a3b8',
    marginTop: 4,
    textAlign: 'center',
  },
  card: {
    backgroundColor: '#0f172a',
    borderRadius: 16,
    padding: 20,
    borderWidth: 1,
    borderColor: '#1e293b',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 5,
  },
  cardTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#ffffff',
    marginBottom: 16,
  },
  errorBanner: {
    backgroundColor: '#450a0a',
    borderColor: '#991b1b',
    borderWidth: 1,
    padding: 10,
    borderRadius: 8,
    marginBottom: 16,
  },
  errorText: {
    color: '#f87171',
    fontSize: 12,
  },
  inputGroup: {
    marginBottom: 14,
  },
  label: {
    fontSize: 12,
    fontWeight: '600',
    color: '#cbd5e1',
    marginBottom: 6,
  },
  input: {
    backgroundColor: '#020617',
    borderWidth: 1,
    borderColor: '#334155',
    borderRadius: 10,
    padding: 12,
    color: '#ffffff',
    fontSize: 14,
  },
  loginButton: {
    backgroundColor: '#0284c7',
    padding: 14,
    borderRadius: 10,
    alignItems: 'center',
    marginTop: 8,
  },
  loginButtonText: {
    color: '#ffffff',
    fontSize: 15,
    fontWeight: 'bold',
  },
  presetHeading: {
    fontSize: 11,
    fontWeight: 'bold',
    color: '#64748b',
    marginTop: 20,
    marginBottom: 10,
    letterSpacing: 1,
  },
  presetsGrid: {
    gap: 8,
  },
  presetButton: {
    backgroundColor: '#1e293b',
    padding: 10,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#334155',
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  presetName: {
    color: '#f1f5f9',
    fontSize: 13,
    fontWeight: '600',
  },
  presetRole: {
    color: '#38bdf8',
    fontSize: 11,
  },
  footerText: {
    textAlign: 'center',
    color: '#475569',
    fontSize: 11,
    marginTop: 24,
  },
});
