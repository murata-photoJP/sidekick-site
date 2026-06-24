// =============================================================
// Sidekick Firebase 設定ファイル
// console.firebase.google.com → プロジェクト設定 → マイアプリ → 構成
// 以下の値を Firebase コンソールから取得して入力してください
// =============================================================
const FIREBASE_CONFIG = {
  apiKey:            "AIzaSyAxN8GUIsdlI6GJdpPPEZo8Ama9zOFFIoY",
  authDomain:        "sidekick-6cfee.firebaseapp.com",
  projectId:         "sidekick-6cfee",
  storageBucket:     "sidekick-6cfee.firebasestorage.app",
  messagingSenderId: "408609587167",
  appId:             "1:408609587167:web:f5c713b847bb34d8fc4e6a",
  measurementId:     "G-SBJEMRYFZQ"
};
// =============================================================

if (!firebase.apps.length) {
  firebase.initializeApp(FIREBASE_CONFIG);
}
