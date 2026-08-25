import logging
import re
import os
from typing import Dict, Any, List, Optional, Tuple
from collections import Counter
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import nltk
    from nltk.sentiment import SentimentIntensityAnalyzer
    from nltk.tokenize import word_tokenize, sent_tokenize
    from nltk.corpus import stopwords
    from nltk.stem import WordNetLemmatizer
    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

try:
    from transformers import pipeline
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.decomposition import LatentDirichletAllocation
    SKLEARN_NLP_AVAILABLE = True
except ImportError:
    SKLEARN_NLP_AVAILABLE = False


class NLPEngine:
    def __init__(self):
        self.sia = None
        self.lemmatizer = None
        self.stop_words = set()
        self.nlp = None
        self.summarizer = None
        self._initialize()

    def _initialize(self):
        if NLTK_AVAILABLE:
            try:
                self.sia = SentimentIntensityAnalyzer()
            except Exception:
                nltk.download("vader_lexicon", quiet=True)
                self.sia = SentimentIntensityAnalyzer()

            try:
                nltk.download("punkt_tab", quiet=True)
                nltk.download("punkt", quiet=True)
                nltk.download("stopwords", quiet=True)
                nltk.download("wordnet", quiet=True)
                nltk.download("averaged_perceptron_tagger", quiet=True)
            except Exception:
                pass

            self.lemmatizer = WordNetLemmatizer()
            try:
                self.stop_words = set(stopwords.words("english"))
            except Exception:
                self.stop_words = set()

        if SPACY_AVAILABLE:
            try:
                self.nlp = spacy.load("en_core_web_sm")
            except Exception:
                try:
                    os.system("python -m spacy download en_core_web_sm")
                    self.nlp = spacy.load("en_core_web_sm")
                except Exception:
                    self.nlp = None

        if TRANSFORMERS_AVAILABLE:
            try:
                self.summarizer = pipeline(
                    "summarization", model="sshleifer/distilbart-cnn-12-6"
                )
            except Exception:
                self.summarizer = None

    def detect_language(self, text: str) -> str:
        if not text.strip():
            return "unknown"

        try:
            non_ascii = sum(1 for c in text if ord(c) > 127)
            total = len(text.replace(" ", ""))
            if total > 0 and non_ascii / total > 0.3:
                return "non-english"
            return "english"
        except Exception:
            return "unknown"

    def sentiment_analysis(self, text: str) -> Dict[str, Any]:
        if not self.sia:
            return {"error": "Sentiment analyzer not available"}

        scores = self.sia.polarity_scores(text)

        if scores["compound"] >= 0.05:
            label = "positive"
        elif scores["compound"] <= -0.05:
            label = "negative"
        else:
            label = "neutral"

        return {
            "sentiment": label,
            "positive_score": scores["pos"],
            "negative_score": scores["neg"],
            "neutral_score": scores["neu"],
            "compound_score": scores["compound"],
        }

    def extract_entities(self, text: str) -> List[Dict[str, str]]:
        if not self.nlp:
            return self._fallback_entities(text)

        doc = self.nlp(text)
        entities = []
        for ent in doc.ents:
            entities.append(
                {"text": ent.text, "label": ent.label_, "start": ent.start_char, "end": ent.end_char}
            )
        return entities

    def _fallback_entities(self, text: str) -> List[Dict[str, str]]:
        entities = []

        email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        for match in re.finditer(email_pattern, text):
            entities.append({"text": match.group(), "label": "EMAIL", "start": match.start(), "end": match.end()})

        url_pattern = r"https?://[^\s]+"
        for match in re.finditer(url_pattern, text):
            entities.append({"text": match.group(), "label": "URL", "start": match.start(), "end": match.end()})

        money_pattern = r"\$\d+(?:,\d{3})*(?:\.\d{2})?"
        for match in re.finditer(money_pattern, text):
            entities.append({"text": match.group(), "label": "MONEY", "start": match.start(), "end": match.end()})

        return entities

    def tokenize(self, text: str) -> List[str]:
        if NLTK_AVAILABLE:
            try:
                return word_tokenize(text.lower())
            except Exception:
                pass
        return text.lower().split()

    def remove_stopwords(self, tokens: List[str]) -> List[str]:
        return [t for t in tokens if t not in self.stop_words and len(t) > 2]

    def lemmatize_tokens(self, tokens: List[str]) -> List[str]:
        if self.lemmatizer:
            return [self.lemmatizer.lemmatize(t) for t in tokens]
        return tokens

    def preprocess(self, text: str) -> Dict[str, Any]:
        tokens = self.tokenize(text)
        filtered = self.remove_stopwords(tokens)
        lemmatized = self.lemmatize_tokens(filtered)

        return {
            "original": text,
            "tokens": tokens,
            "filtered_tokens": filtered,
            "lemmatized_tokens": lemmatized,
            "token_count": len(tokens),
            "unique_tokens": len(set(tokens)),
        }

    def summarize(self, text: str, max_length: int = 130, min_length: int = 30) -> str:
        if self.summarizer:
            try:
                result = self.summarizer(
                    text, max_length=max_length, min_length=min_length, do_sample=False
                )
                return result[0]["summary_text"]
            except Exception as e:
                logger.warning(f"Transformer summarization failed: {e}")

        return self._extractive_summary(text, max_length)

    def _extractive_summary(self, text: str, max_length: int = 130) -> str:
        if NLTK_AVAILABLE:
            try:
                sentences = sent_tokenize(text)
            except Exception:
                sentences = text.split(". ")
        else:
            sentences = text.split(". ")

        if len(sentences) <= 2:
            return text

        word_freq = Counter()
        for sentence in sentences:
            words = self.tokenize(sentence)
            words = self.remove_stopwords(words)
            word_freq.update(words)

        if not word_freq:
            return ". ".join(sentences[:3])

        max_freq = max(word_freq.values()) if word_freq else 1
        for word in word_freq:
            word_freq[word] = word_freq[word] / max_freq

        sentence_scores = {}
        for i, sentence in enumerate(sentences):
            words = self.tokenize(sentence)
            filtered = self.remove_stopwords(words)
            score = sum(word_freq.get(w, 0) for w in filtered)
            sentence_scores[i] = score / len(filtered) if filtered else 0

        top_sentences = sorted(sentence_scores, key=sentence_scores.get, reverse=True)[:3]
        top_sentences.sort()

        return ". ".join([sentences[i] for i in top_sentences])

    def topic_modeling(self, texts: List[str], n_topics: int = 5) -> Dict[str, Any]:
        if not SKLEARN_NLP_AVAILABLE:
            return {"error": "scikit-learn not available for topic modeling"}

        if len(texts) < n_topics:
            return {"error": f"Need at least {n_topics} documents for {n_topics} topics"}

        vectorizer = TfidfVectorizer(max_features=1000, stop_words="english")
        tfidf_matrix = vectorizer.fit_transform(texts)

        lda = LatentDirichletAllocation(
            n_components=n_topics, random_state=42, max_iter=10
        )
        lda.fit(tfidf_matrix)

        feature_names = vectorizer.get_feature_names_out()
        topics = []
        for idx, topic in enumerate(lda.components_):
            top_words_idx = topic.argsort()[-10:][::-1]
            top_words = [feature_names[i] for i in top_words_idx]
            topics.append({"topic_id": idx, "words": top_words, "weight": float(topic.sum())})

        document_topics = lda.transform(tfidf_matrix)
        dominant_topics = [
            int(topic.argmax()) for topic in document_topics
        ]

        return {
            "n_topics": n_topics,
            "topics": topics,
            "document_topic_assignments": dominant_topics,
        }

    def text_classification(
        self, texts: List[str], labels: List[str]
    ) -> Dict[str, Any]:
        if not SKLEARN_NLP_AVAILABLE:
            return {"error": "scikit-learn not available"}

        if len(texts) != len(labels):
            return {"error": "Texts and labels must have the same length"}

        if len(set(labels)) < 2:
            return {"error": "Need at least 2 different labels for classification"}

        vectorizer = TfidfVectorizer(max_features=5000, stop_words="english")
        X = vectorizer.fit_transform(texts)

        from sklearn.model_selection import train_test_split
        from sklearn.naive_bayes import MultinomialNB
        from sklearn.metrics import accuracy_score, classification_report

        X_train, X_test, y_train, y_test = train_test_split(
            X, labels, test_size=0.2, random_state=42
        )

        model = MultinomialNB()
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)

        return {
            "accuracy": round(accuracy_score(y_test, y_pred), 4),
            "report": classification_report(y_test, y_pred, output_dict=True),
            "model_type": "MultinomialNB",
            "train_size": len(X_train),
            "test_size": len(X_test),
        }

    def get_stats(self) -> Dict[str, Any]:
        return {
            "nltk_available": NLTK_AVAILABLE,
            "spacy_available": SPACY_AVAILABLE,
            "transformers_available": TRANSFORMERS_AVAILABLE,
            "sentiment_analyzer": self.sia is not None,
            "ner_model": self.nlp is not None,
            "summarizer": self.summarizer is not None,
        }