
import unittest
import math
from vibecode.rag import VibeIndex, _cosine_similarity, _normalize_vector

# Mock embedding function to avoid API calls
def mock_get_embedding(text):
    # Simple consistent embedding based on character codes
    # "apple" -> [1, 0]
    # "apply" -> [0.9, 0.1]
    # "orange" -> [0, 1]
    
    if "apple" in text:
        return [1.0, 0.0]
    if "apply" in text:
        return [0.9, 0.4] # Not normalized yet
    if "orange" in text:
        return [0.0, 1.0]
    return [0.5, 0.5]

class TestVibeRAGThreshold(unittest.TestCase):
    def setUp(self):
        # Monkey patch get_embedding
        import vibecode.rag
        self.original_embed = vibecode.rag.get_embedding
        vibecode.rag.get_embedding = mock_get_embedding
        
        self.index = VibeIndex()
        # Add files with known "embeddings"
        # apple.txt -> [1, 0]
        # apply.txt -> [0.9, 0.4] -> normalized ~ [0.91, 0.41]
        # orange.txt -> [0, 1]
        self.index.add_file("apple.txt", "apple")
        self.index.add_file("apply.txt", "apply") 
        self.index.add_file("orange.txt", "orange")

    def tearDown(self):
        import vibecode.rag
        vibecode.rag.get_embedding = self.original_embed

    def test_search_threshold(self):
        # Query "apple" -> [1, 0]
        # Similarity to apple.txt: 1.0
        # Similarity to apply.txt: high (~0.9)
        # Similarity to orange.txt: 0.0
        
        # 1. No threshold (should get all)
        results = self.index.search("apple", top_k=10, min_score=0.0)
        self.assertEqual(len(results), 3)
        
        # 2. High threshold (should exclude orange)
        results = self.index.search("apple", top_k=10, min_score=0.5)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0][0], "apple.txt")
        self.assertEqual(results[1][0], "apply.txt")
        
        # 3. Very high threshold (should only get apple)
        results = self.index.search("apple", top_k=10, min_score=0.95)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], "apple.txt")

    def test_find_related_threshold(self):
        # Find related to "apple.txt"
        
        # 1. Threshold 0.5 (should exclude orange)
        results = self.index.find_related("apple.txt", min_score=0.5)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], "apply.txt")
        
        # 2. Threshold 0.0 (should include orange)
        results = self.index.find_related("apple.txt", min_score=0.0)
        # Should be 2 (apply, orange). Apple excluded as source.
        self.assertEqual(len(results), 2)

if __name__ == "__main__":
    unittest.main()
