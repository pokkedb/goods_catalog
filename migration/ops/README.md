# systemdサービス化（常時稼働）

`inventory-app`と同じ方式。backend/frontendをsystemdサービスとして登録すると、
ターミナルを閉じても・サーバー再起動後も自動で起動する（`Restart=always` + `WantedBy=multi-user.target`）。

適用にはsudoが必要なため、以下を人間が実行すること。

```bash
sudo cp goods-catalog-backend.service goods-catalog-frontend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now goods-catalog-backend
sudo systemctl enable --now goods-catalog-frontend
```

適用後、今手動で起動しているターミナルの`uvicorn`・`npm run dev`は止めてよい（`Ctrl+C`）。

## 動作確認

```bash
systemctl status goods-catalog-backend goods-catalog-frontend
```

## ログの確認

```bash
journalctl -u goods-catalog-backend -f
journalctl -u goods-catalog-frontend -f
```

## 停止・無効化したい場合

```bash
sudo systemctl disable --now goods-catalog-backend goods-catalog-frontend
```
