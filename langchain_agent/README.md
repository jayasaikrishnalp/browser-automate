# సింపుల్ లాంగ్‌చెయిన్ ఏజెంట్ (Simple LangChain Agent)

ఈ ప్రాజెక్ట్ ఒక సింపుల్ లాంగ్‌చెయిన్ ఏజెంట్ ని ఉపయోగించి OpenAI లేదా Anthropic మోడల్స్ తో పని చేస్తుంది. 

## ఫీచర్లు

- OpenAI GPT-3.5-Turbo లేదా Anthropic Claude ఉపయోగించగలరు
- సెర్చ్ మరియు కాల్క్యులేషన్ టూల్స్ తో ఏజెంట్ పని చేస్తుంది
- డాట్‌ఎన్వి ఫైల్ ద్వారా కాన్ఫిగరేషన్ సెట్టింగ్స్ మార్చవచ్చు

## సెటప్ (Setup)

1. ఈ రెపో ని క్లోన్ చేసుకోండి

2. అవసరమైన ప్యాకేజీలను ఇన్‌స్టాల్ చేసుకోండి:
   ```
   pip install -r requirements.txt
   ```

3. `.env` ఫైల్ ని సెటప్ చేసుకోండి:
   ```
   # OpenAI లేదా Anthropic API కీని సెట్ చేసుకోండి
   OPENAI_API_KEY=your_openai_api_key_here
   ANTHROPIC_API_KEY=your_anthropic_api_key_here
   
   # ఏ మోడల్ ఉపయోగించాలో సెట్ చేసుకోండి
   USE_ANTHROPIC=false  # Anthropic వాడటానికి "true" గా మార్చండి
   TEMPERATURE=0.7
   VERBOSE=true
   ```

## ఉపయోగించడం (Usage)

స్క్రిప్ట్ ని రన్ చేయడానికి:

```
python simple_agent.py
```

ఏజెంట్ ఎలా పని చేస్తుందో ఉదాహరణలు:

1. సమాచారం అడగండి:
   ```
   👤 Enter your query: ప్రస్తుతం అమెరికా అధ్యక్షుడు ఎవరు?
   ```

2. లెక్కలు చేయించండి:
   ```
   👤 Enter your query: 25 x 48 ఎంత?
   ```

## కస్టమైజేషన్

మీ స్వంత టూల్స్ ని జోడించడానికి, `simple_agent.py` ఫైల్ లో `@tool` డెకొరేటర్ తో కొత్త ఫంక్షన్లను జోడించండి.

ఉదాహరణ:
```python
@tool
def translate_text(text: str, target_language: str) -> str:
    """Translate text to a target language."""
    # Translation logic
    return f"Translated '{text}' to {target_language}"
``` 