import sys

from search import Search


def test_exists(query: str, collection: str = "SO"):
    s = Search(collection)
    s._limit = 0
    res = s.exists(query)
    for d in res:
        print(d)


def fuzzy_search(query: str, collection: str = "SO"):
    s = Search(collection)
    s._limit = 10
    res = s.fuzzy_search(query)
    for d in res:
        print(d)

def test_chars():
    alphabet = "0123456789AaÁáBbCcDdÐðEeÉéFfGgHhIiÍíJjKkLlMmNnOoÓóPpQqRrSsTtUuÚúVvWwXxYyÝýZzÞþÆæÖöØøßÅå -"
    for item in alphabet:
        # print(f"item: {ord(item)} '{item}'")
        if ord(item) >= 65 and ord(item) <= 90 or ord(item) >= 192 and ord(item) <= 222:
            print(f"  U -> L {ord(item)}, '{item}' -> '{chr(ord(item)+32)}'")
        elif ord(item) >= 97 and ord(item) <= 122 or ord(item) >= 224 and ord(item) <= 254:
            print(f"  L -> U {ord(item)}, '{item}' -> '{chr(ord(item)-32)}'")
        else:
            print(f"  other character {ord(item)}, '{item}'")
        

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python testing.py <query>")
        sys.exit(1)
    query = sys.argv[1]
    collection = sys.argv[2] if len(sys.argv) > 2 else "SO"
    # test_exists(query, collection)
    # fuzzy_search(query, collection)
    # list_collections()
    test_chars()
    
