// File generated from Firebase project: amr-system-nav
// Project: AMR Navigation System
// Database: https://amr-system-nav-default-rtdb.asia-southeast1.firebasedatabase.app

import 'package:firebase_core/firebase_core.dart' show FirebaseOptions;
import 'package:flutter/foundation.dart'
    show defaultTargetPlatform, kIsWeb, TargetPlatform;

class DefaultFirebaseOptions {
  static FirebaseOptions get currentPlatform {
    if (kIsWeb) {
      return web;
    }
    switch (defaultTargetPlatform) {
      case TargetPlatform.android:
        return android;
      case TargetPlatform.iOS:
        return ios;
      default:
        // Desktop / other — fall back to web config for dev purposes
        return web;
    }
  }

  // Web SDK config (also used as fallback for desktop dev)
  static const FirebaseOptions web = FirebaseOptions(
    apiKey: 'AIzaSyDUKE5pX95NxQWTbnLzK6tZSZW9cDg77hI',
    appId: '1:381119183118:web:d42c36f2b4aaa8ffac7f5f',
    messagingSenderId: '381119183118',
    projectId: 'amr-system-nav',
    authDomain: 'amr-system-nav.firebaseapp.com',
    databaseURL: 'https://amr-system-nav-default-rtdb.asia-southeast1.firebasedatabase.app',
    storageBucket: 'amr-system-nav.firebasestorage.app',
  );

  // Android
  static const FirebaseOptions android = FirebaseOptions(
    apiKey: 'AIzaSyDUKE5pX95NxQWTbnLzK6tZSZW9cDg77hI',
    appId: '1:381119183118:web:d42c36f2b4aaa8ffac7f5f',
    messagingSenderId: '381119183118',
    projectId: 'amr-system-nav',
    databaseURL: 'https://amr-system-nav-default-rtdb.asia-southeast1.firebasedatabase.app',
    storageBucket: 'amr-system-nav.firebasestorage.app',
  );

  // iOS — add GoogleService-Info.plist and update appId when registering iOS app
  static const FirebaseOptions ios = FirebaseOptions(
    apiKey: 'AIzaSyDUKE5pX95NxQWTbnLzK6tZSZW9cDg77hI',
    appId: '1:381119183118:web:d42c36f2b4aaa8ffac7f5f',
    messagingSenderId: '381119183118',
    projectId: 'amr-system-nav',
    databaseURL: 'https://amr-system-nav-default-rtdb.asia-southeast1.firebasedatabase.app',
    storageBucket: 'amr-system-nav.firebasestorage.app',
    iosBundleId: 'com.example.amrNavigation',
  );
}
