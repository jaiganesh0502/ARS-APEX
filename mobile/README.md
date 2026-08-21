# 📱 Alta Hospital Care — React Native Mobile Application

Full-featured native mobile client for **Alta Discharge & Inter-Hospital Transfer Orchestration Platform**, built with **React Native**, **Expo**, and **TypeScript**.

---

## 🌟 Key Features

- **Physician Ward Rounds & Decision Triage**: Bedside discharge/transfer sign-offs with instant AI summary access.
- **Inter-Hospital Transfers & Bed Reservation**: Real-time acceptance and receiving hospital bed allocation for Dr. Elena.
- **Live ALS & Standard Ambulance Telemetry**: Real-time GPS distance, vehicle plate, driver details, and ETA tracking.
- **Patient Care & 1-Click UPI Payment**: Personalized recovery plan, itemized billing, and instant UPI checkout simulation.
- **JWT Bearer RBAC Authentication**: Strict multi-persona access control matching the web suite.

---

## 🚀 Getting Started

### 1. Prerequisites
- Node.js 18+ or 20+
- [Expo Go](https://expo.dev/client) app installed on your physical iOS/Android device (or Android Studio / Xcode simulator).

### 2. Installation
```bash
cd mobile
npm install
```

### 3. Start Development Server
```bash
npm start
```
- Press `a` to launch in Android Emulator.
- Press `i` to launch in iOS Simulator.
- Scan the QR code using the **Expo Go** app on your physical Android or iPhone to run immediately!

---

## 📦 Building Standalone APK / iOS Binary

To build a standalone APK or iOS IPA file with EAS:
```bash
# Install EAS CLI
npm install -g eas-cli

# Login to Expo
eas login

# Build Android APK
eas build -p android --profile preview
```
