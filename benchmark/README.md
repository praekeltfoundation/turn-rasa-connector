Running Benchmarks
------------------
You'll need an actual Rasa bot to run the benchmarks against.

Add something similar to this in `credentials.yaml`
```yaml
turn_rasa_connector.turn.TurnInput:
  url: "http://localhost:8080"
  token: "test-token"
```

And then you can run the mock turn server:
```bash
python benchmark/fake_turn.py
```

You can then use a tool like [vegeta](https://github.com/tsenart/vegeta) to make requests to test how much load the bot will be able to handle:
```bash
jq -ncM 'while(true; .+1) | {method: "POST", url: "http://:5005/webhooks/turn/webhook/", body: {messages: [{from: ( . | tostring ) , text: { body: "check" }, id: ( . | tostring ), type: "text"}]} | @base64 }' | vegeta attack -rate=10/s -format=json -duration=600s --max-connections=500 -lazy | tee results.bin | vegeta report
```
