other = Library()
a = other.dogs
b = other.get_all()
a.pop()
b.pop()

with open("examples/api.py", "r") as file:
    data = file.read()

mnode = MNode("local")  # create file name for given source code
mnode.source = data
mnode.gen_ast()  # build abstract syntax tree
cfg = mnode.gen_cfg()
m_ssa = SSA()
ssa_results, const_dict = m_ssa.compute_SSA(cfg)
