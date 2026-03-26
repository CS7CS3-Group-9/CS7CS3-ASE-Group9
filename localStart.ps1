$backendCmd = '$env:GOOGLE_MAPS_API_KEY=''AIzaSyB0NyaxFeJf26YUQBz9nKakijCRAisxRiw''; $env:TOMTOM_API_KEY=''hkRIaqbdLM2w5sujd4yq4CwPfWjoJupg''; $env:ENABLE_FIRESTORE=''false''; $env:BIKES_MODEL_PATH=''backend\ml\artifacts\bikes_model.joblib''; python -m flask --app backend.app:create_app --debug run --port 5000'
 
$frontendCmd = '$env:BACKEND_API_URL=''http://localhost:5000''; $env:DASHBOARD_USERS_FILE=''frontend/users.json''; $env:SECRET_KEY=''change-me''; python -m flask --app frontend.app:create_app --debug run --port 8080'
 
Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd
Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd