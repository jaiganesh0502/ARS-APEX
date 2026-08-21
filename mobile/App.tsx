import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { AuthProvider, useAuth } from './src/context/AuthContext';
import { LoginScreen } from './src/screens/LoginScreen';
import { DoctorDashboardScreen } from './src/screens/DoctorDashboardScreen';
import { TransfersScreen } from './src/screens/TransfersScreen';
import { PatientPortalScreen } from './src/screens/PatientPortalScreen';
import { ActivityIndicator, View } from 'react-native';

const Stack = createNativeStackNavigator();
const Tab = createBottomTabNavigator();

function StaffTabs() {
  return (
    <Tab.Navigator
      screenOptions={{
        headerShown: false,
        tabBarStyle: {
          backgroundColor: '#0f172a',
          borderTopColor: '#1e293b',
        },
        tabBarActiveTintColor: '#38bdf8',
        tabBarInactiveTintColor: '#64748b',
      }}
    >
      <Tab.Screen name="Dashboard" component={DoctorDashboardScreen} />
      <Tab.Screen name="Transfers" component={TransfersScreen} />
    </Tab.Navigator>
  );
}

function NavigationRoot() {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <View style={{ flex: 1, backgroundColor: '#020617', justifyContent: 'center', alignItems: 'center' }}>
        <ActivityIndicator size="large" color="#0284c7" />
      </View>
    );
  }

  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      {!user ? (
        <Stack.Screen name="Login" component={LoginScreen} />
      ) : user.role === 'patient' ? (
        <Stack.Screen name="PatientPortal" component={PatientPortalScreen} />
      ) : (
        <Stack.Screen name="StaffApp" component={StaffTabs} />
      )}
    </Stack.Navigator>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <NavigationContainer>
        <NavigationRoot />
      </NavigationContainer>
    </AuthProvider>
  );
}
