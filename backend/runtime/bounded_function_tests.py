"""Finite integer Python-syntax evaluation. Never execute generated Python."""
import ast
import hashlib
import json

TOOL = 'code.function.check@1.0.0'
PROFILE = 'bounded_batch_size.v1'
EVALUATOR = 'integer-ast-v1'
SCOPE = 'Finite integer Python-syntax subset and fixed owner cases only; not CPython or arbitrary repository tests'
EXECUTOR_SCOPE = 'bounded arithmetic AST interpreter; not CPython/arbitrary repo'
PARAMETERS = ('requested', 'pending', 'hard_limit')
MINIMUM, MAXIMUM = -(2**31), 2**31-1
# Immutable release catalog, outside every model-writable workspace.
CASES = (
 ((10,100,25),10),((100,10,25),10),((100,100,25),25),((0,100,25),0),
 ((-1,100,25),0),((10,-1,25),0),((10,100,-1),0),((1,1,1),1),
 ((20,20,20),20),((5,6,7),5),((7,5,6),5),((6,7,5),5),
 ((0,0,0),0),((-1,-1,-1),0),((100,0,25),0),((10,100,0),0),
 ((MAXIMUM,MAXIMUM,MAXIMUM),MAXIMUM),((MINIMUM,MAXIMUM,MAXIMUM),0),
 ((MAXIMUM,MINIMUM,MAXIMUM),0),((MAXIMUM,MAXIMUM,MINIMUM),0),
 ((MAXIMUM,3,MAXIMUM),3),((3,MAXIMUM,MAXIMUM),3),((MAXIMUM,MAXIMUM,3),3),
 ((2,3,1),1),((1,2,3),1),((3,1,2),1),
)

def digest(data):
    return hashlib.sha256(data).hexdigest()

def profile_hash(profile_id=PROFILE):
    if profile_id != PROFILE: raise ValueError('Unknown immutable case profile')
    return digest(json.dumps({'id':PROFILE,'parameters':PARAMETERS,'cases':CASES},sort_keys=True,separators=(',',':')).encode())

def integer(value):
    if type(value) is not int or not MINIMUM <= value <= MAXIMUM:
        raise ValueError('Only signed 32-bit integers are supported')
    return value

class Interpreter:
    def __init__(self, source):
        tree=ast.parse(source)
        stack=[(tree,0)]; count=0
        while stack:
            node,depth=stack.pop();count+=1
            if depth>32 or count>256:raise ValueError('AST structural budget exceeded')
            stack.extend((child,depth+1) for child in ast.iter_child_nodes(node))
        if len(tree.body)!=1 or not isinstance(tree.body[0],ast.FunctionDef):raise ValueError('Supply one function only')
        self.function=f=tree.body[0];a=f.args
        if (f.name!='bounded_batch_size' or f.decorator_list or f.returns or f.type_comment or getattr(f,'type_params',[])
                or a.posonlyargs or a.vararg or a.kwarg or a.kwonlyargs or a.defaults or a.kw_defaults
                or tuple(arg.arg for arg in a.args)!=PARAMETERS or any(arg.annotation or arg.type_comment for arg in a.args)):
            raise ValueError('Function signature is not the reviewed contract')
        self.validate_block(f.body,set(PARAMETERS))

    def validate_expression(self,node,bound):
        if isinstance(node,ast.Constant):integer(node.value)
        elif isinstance(node,ast.Name):
            if node.id not in bound:raise ValueError('Unbound name')
        elif isinstance(node,ast.BinOp) and isinstance(node.op,(ast.Add,ast.Sub)):
            self.validate_expression(node.left,bound);self.validate_expression(node.right,bound)
        elif isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.USub,ast.UAdd,ast.Not)):
            self.validate_expression(node.operand,bound)
        elif isinstance(node,ast.Compare) and all(isinstance(op,(ast.Lt,ast.LtE,ast.Gt,ast.GtE,ast.Eq,ast.NotEq)) for op in node.ops):
            for operand in [node.left,*node.comparators]:self.validate_expression(operand,bound)
        elif isinstance(node,ast.BoolOp) and isinstance(node.op,(ast.And,ast.Or)):
            for operand in node.values:self.validate_expression(operand,bound)
        elif isinstance(node,ast.IfExp):
            for operand in (node.test,node.body,node.orelse):self.validate_expression(operand,bound)
        elif (isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in {'min','max'}
              and not node.keywords and 2<=len(node.args)<=4):
            for operand in node.args:self.validate_expression(operand,bound)
        else:raise ValueError('Unsupported syntax')

    def validate_block(self,body,bound):
        bound=set(bound)
        for node in body:
            if isinstance(node,ast.Return) and node.value is not None:self.validate_expression(node.value,bound)
            elif isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name):
                name=node.targets[0].id
                if name.startswith('_') or name in {'min','max'}:raise ValueError('Reserved assignment name')
                self.validate_expression(node.value,bound);bound.add(name)
            elif isinstance(node,ast.If):
                self.validate_expression(node.test,bound)
                bound |= self.validate_block(node.body,bound) & self.validate_block(node.orelse,bound)
            else:raise ValueError('Unsupported statement')
        return bound

    def expression(self,node,env):
        self.fuel-=1
        if self.fuel<0:raise ValueError('Evaluation budget exceeded')
        if isinstance(node,ast.Constant):return integer(node.value)
        if isinstance(node,ast.Name):return integer(env[node.id])
        if isinstance(node,ast.BinOp):
            left,right=integer(self.expression(node.left,env)),integer(self.expression(node.right,env))
            return integer(left+right if isinstance(node.op,ast.Add) else left-right)
        if isinstance(node,ast.UnaryOp):
            value=self.expression(node.operand,env)
            if isinstance(node.op,ast.Not):return not value
            return integer(-integer(value) if isinstance(node.op,ast.USub) else integer(value))
        if isinstance(node,ast.Compare):
            left=integer(self.expression(node.left,env))
            for operator,operand in zip(node.ops,node.comparators):
                right=integer(self.expression(operand,env))
                value=left<right if isinstance(operator,ast.Lt) else left<=right if isinstance(operator,ast.LtE) else left>right if isinstance(operator,ast.Gt) else left>=right if isinstance(operator,ast.GtE) else left==right if isinstance(operator,ast.Eq) else left!=right
                if not value:return False
                left=right
            return True
        if isinstance(node,ast.BoolOp):
            value=self.expression(node.values[0],env)
            for operand in node.values[1:]:
                if (isinstance(node.op,ast.And) and not value) or (isinstance(node.op,ast.Or) and value):break
                value=self.expression(operand,env)
            return value
        if isinstance(node,ast.IfExp):return self.expression(node.body if self.expression(node.test,env) else node.orelse,env)
        if isinstance(node,ast.Call):
            values=[integer(self.expression(operand,env)) for operand in node.args]
            return min(values) if node.func.id=='min' else max(values)
        raise ValueError('Unsupported expression')

    def block(self,body,env):
        for node in body:
            self.fuel-=1
            if self.fuel<0:raise ValueError('Evaluation budget exceeded')
            if isinstance(node,ast.Return):return True,integer(self.expression(node.value,env))
            if isinstance(node,ast.Assign):env[node.targets[0].id]=integer(self.expression(node.value,env))
            elif isinstance(node,ast.If):
                returned,value=self.block(node.body if self.expression(node.test,env) else node.orelse,env)
                if returned:return True,value
        return False,None

    def run(self,args):
        if type(args) is not tuple or len(args)!=3:raise ValueError('Immutable integer tuple required')
        self.fuel=4096
        returned,value=self.block(self.function.body,dict(zip(PARAMETERS,map(integer,args))))
        if not returned:raise ValueError('Function returned no integer')
        return value

def check_function(params):
    if type(params) is not dict or set(params)!={'source','profile_id'}:raise ValueError('Use source and immutable profile only')
    source=params['source'];profile=params['profile_id'];cases_hash=profile_hash(profile)
    if not isinstance(source,str) or len(source.encode())>8192:raise ValueError('Source exceeds 8 KiB')
    result={'accepted':False,'exit_code':1,'source_sha256':digest(source.encode()),'profile_id':profile,
            'cases_sha256':cases_hash,'evaluator_version':EVALUATOR,'cases_run':0,'cases_passed':0,
            'scope':SCOPE,'executor_scope':EXECUTOR_SCOPE,'failures':[]}
    try:interpreter=Interpreter(source)
    except (SyntaxError,ValueError,RecursionError):return dict(result,error_code='unsupported_candidate')
    for index,(args,expected) in enumerate(CASES):
        result['cases_run']+=1
        try:actual=interpreter.run(args)
        except (ValueError,KeyError,RecursionError):
            if len(result['failures'])<4:result['failures'].append({'case':index,'error_code':'invalid_integer_evaluation'})
            continue
        if actual==expected:result['cases_passed']+=1
        elif len(result['failures'])<4:result['failures'].append({'case':index,'arguments':list(args),'expected':expected,'actual':actual})
    result.update(accepted=result['cases_passed']==len(CASES),exit_code=0 if result['cases_passed']==len(CASES) else 1)
    return result

def validated_acceptance(engine,mission_id,version,step_id):
    """Only current approved mission, retained execution evidence and current file bytes pass."""
    try:
        state=engine.missions.get(mission_id)
        if type(version) is not int or state['version']!=version or state['approved_version']!=version or state['status'] not in {'running','completed'}:raise ValueError('Stale mission')
        step=next(s for s in state['plan']['steps'] if s['id']==step_id)
        if step['kind']!='function_check' or step['case_profile_sha256']!=profile_hash(step['case_profile']):raise ValueError('Unreviewed case profile')
        task=engine.tasks.get(state['steps'][step_id]['task_id'])
        if task['status'].lower()!='completed' or task['metadata'].get('tool')!=TOOL:raise ValueError('No completed acceptance execution')
        for key,value in {'mission_id':mission_id,'mission_version':version,'step_id':step_id}.items():
            if task['metadata'].get(key)!=value:raise ValueError('Mission receipt binding mismatch')
        from backend.swarm.manager import execution_request
        from backend.runtime.execution import verify_request_result
        def verified(current,tool):
            if current['status'].lower()!='completed' or current['metadata']['tool']!=tool:raise ValueError('Missing governed source evidence')
            if current['metadata']['mission_id']!=mission_id or current['metadata']['mission_version']!=version:raise ValueError('Source mission mismatch')
            item,=current['result']['results'];plan=current['result']['plan'];subtask,=plan['subtasks']
            if item['verification']['state']!='VERIFIED' or plan['task_id']!=current['id'] or subtask['prompt']!=current['prompt'] or subtask['knight']!=item['knight']:raise ValueError('Execution plan mismatch')
            verify_request_result(execution_request(current,subtask['prompt']),item['outcome'])
            return item['outcome']['output']
        output=verified(task,TOOL)
        if output['accepted'] is not True or output['profile_id']!=step['case_profile']:raise ValueError('Acceptance failed')
        source_step=next(s for s in state['plan']['steps'] if s['id']==step['repair_source'])
        read_step=next(s for s in state['plan']['steps'] if s['id']==step['input_from'])
        if read_step['kind']!='read_file' or read_step['path']!=source_step['path']:raise ValueError('Unbound source read')
        written=verified(engine.tasks.get(state['steps'][source_step['id']]['task_id']),'workspace.write@1.0.0')
        read_task=engine.tasks.get(state['steps'][read_step['id']]['task_id'])
        read=verified(read_task,'workspace.read@1.0.0')
        if written['sha256']!=output['source_sha256'] or read['sha256']!=output['source_sha256'] or digest(read['text'].encode())!=output['source_sha256'] or task['metadata']['tool_parameters']['source']!=read['text']:
            raise ValueError('Source write, read and acceptance differ')
        from backend.runtime.computer_tools import workspace_path
        if digest(workspace_path(source_step['path']).read_bytes())!=output['source_sha256']:raise ValueError('Accepted source changed')
        return {key:output[key] for key in ('accepted','source_sha256','profile_id','cases_sha256','evaluator_version','cases_run','cases_passed','scope','executor_scope')} | {'task_id':task['id'],'mission_id':mission_id,'mission_version':version,'step_id':step_id}
    except (KeyError,TypeError,StopIteration,OSError,ValueError) as error:
        raise ValueError('No current independently verified bounded-function acceptance') from error
