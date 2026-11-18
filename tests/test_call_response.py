import importlib.util,json
from pathlib import Path
p=Path(__file__).parents[1]/'backend/server.py';spec=importlib.util.spec_from_file_location('candidate',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.ALLOW_AGENT_MODE=True
m.format_time_context=lambda value:'Test time context'
class Capture(m.SeraWebHandler):
 def send_json(self,status,data):self.result=(status,data)
cases=[(json.dumps({'Goodnight, friend! Sweet dreams.':['neutral',False,'Goodnight, friend! Sweet dreams.']}),True,False),(json.dumps({'expression':'happy','end_call':True,'reply':'Bye, friend!'}),True,True),(json.dumps({'expression':'neutral','end_call':'false','reply':'Hello.'}),True,False),('[expr:happy][call:end] Bye, friend!',True,False),('[expr:neutral] Farewell means goodbye.',True,False),('[expr:neutral] You mentioned [call:end] earlier.',True,False),('[expr:happy][call:end] Bye!',False,False),('[expr:neutral][call:end]',True,False),('<think>[call:end]</think>[expr:neutral] Hello.',True,False)]
for reply,enabled,expected in cases:
 m.run_chat_mode=lambda *args,reply=reply:reply
 spoken=[];m.synthesize_kokoro_wav=lambda text:spoken.append(text) or b'test-wav'
 h=object.__new__(Capture);h.handle_call_chat(json.dumps({'text':'test','call_control':enabled}).encode());code,data=h.result
 assert code==200 and data['end_call']==expected,(reply,data)
 assert '[call:' not in spoken[0] and '[expr:' not in spoken[0],spoken
 assert not spoken[0].startswith(('{','[')),spoken
print('Backend action parsing, opt-in, fail-open, TTS tag removal PASS')

# Exact reported malformed shape: one repair, then safe prose; never repeat tools.
bad=json.dumps({'Goodnight!':['neutral',False,'Goodnight!']})
for mode in ['chat','agent']:
 calls=[];spoken=[]
 def response(*args):calls.append(args);return bad
 m.run_chat_mode=response;m.run_agent_mode=response
 m.synthesize_kokoro_wav=lambda text:spoken.append(text) or b'wav'
 h=object.__new__(Capture);h.handle_call_chat(json.dumps({'text':'goodbye','mode':mode,'call_control':True}).encode())
 assert len(calls)==(2 if mode=='chat' else 1)
 assert spoken==['Sorry, I had trouble with that response. Please try again.']
 assert h.result[1]['end_call'] is False
print('Reported JSON leak rejected; single repair; no repeated Agent tools PASS')

m.ALLOW_AGENT_MODE=False
h=object.__new__(Capture);h.handle_call_chat(json.dumps({'text':'test','mode':'agent'}).encode())
assert h.result[0]==403
print('Agent disabled by default PASS')
