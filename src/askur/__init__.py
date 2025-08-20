
def hello() -> str:
    import sys
    print( sys.executable)
    # search()
    exists()
    find_similar("hestur")

# def search( query:str=None) -> str:
#     import sys
#     print( sys.prefix)

def exists(query:str=None) -> str:
    import sys
    print( sys.version)

def find_similar(query:str) -> str:
    import sys
    print( sys.platform)

def make_lookup(file:str) -> str:
    # import make_lookup
    print(f"Creating lookup for {file}")
    
    


