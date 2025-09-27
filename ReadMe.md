.\retailco\Scripts\Activate.ps1
uvicorn backend.app:app --reload --env-file .env


$headers = @{ "Content-Type" = "application/json" }; $body = '{"session_id":"test-s1","text":"I want to buy the navy casual shirt","channel":"web","user_id":"user123"}'; Invoke-WebRequest -Uri "http://127.0.0.1:8000/chat" -Headers $headers -Method POST -Body $body






$ curl -X POST "https://api.telegram.org/bot8428929226:AAHdtf_9Zz5QVZUpjQX9wTowdHXJIU6fjAI/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://pseudomilitary-ascertainable-toya.ngrok-free.dev/telegram/webhook"}'
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100   140  100    57  100    83     99    144 --:--:-- --:--:-- --:--:--   243{"ok":true,"result":true,"description":"Webhook was set"}

renua@LAPTOP-761D9LGB MINGW64 ~
$ curl "https://api.telegram.org/bot8428929226:AAHdtf_9Zz5QVZUpjQX9wTowdHXJIU6fjAI/getWebhookInfo"
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100   209  100   209    0     0    383      0 --:--:-- --:--:-- --:--:--   385{"ok":true,"result":{"url":"https://pseudomilitary-ascertainable-toya.ngrok-free.dev/telegram/webhook","has_custom_certificate":false,"pending_update_count":0,"max_connections":40,"ip_address":"3.125.209.94"}}



ngrok http 8000       

ngrok config add-authtoken 33Cg8WmCeXo9rtI8GsN6m1UOkHa_UnDPa6DxoV5zocXdJuFK   