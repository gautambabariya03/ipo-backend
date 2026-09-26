import { initializeApp, getApps, getApp } from "firebase/app";
import { initializeAuth, getReactNativePersistence } from "firebase/auth";
import AsyncStorage from "@react-native-async-storage/async-storage";

const firebaseConfig = {
  apiKey: "AIzaSyCIfV9R6QOW-4Bp15e_VShwp1Ll22fvSL8",
  authDomain: "ipo-gmp-tracker-686ca.firebaseapp.com",
  projectId: "ipo-gmp-tracker-686ca",
  storageBucket: "ipo-gmp-tracker-686ca.firebasestorage.app",
  messagingSenderId: "653458012098",
  appId: "1:653458012098:web:b296d56efa51b40b90085b"
};

// Initialize Firebase App
const app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApp();

// Initialize Auth with AsyncStorage Persistence
const auth = initializeAuth(app, {
  persistence: getReactNativePersistence(AsyncStorage)
});

export { app, auth };