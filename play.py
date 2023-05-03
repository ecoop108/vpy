# from vfj import version, at, run
# from slice import slice
# from ast import unparse

# @version(name='start')
# @version(name='full', replaces=['start'])
# class Name:

#     @at('start')
#     def __init__(self, first, last):
#         self.first = first
#         self.last = last

#     @at('full')
#     def __init__(self, full):
#         self.full_name = full

#     @at('full')
#     def get(self):
#         return self.full_name

# print(id(Name))

# @run('start', globals())
# def main():
#     print(id(Name))
#     obj = Name('xxx', 'yyy')
#     print(obj.long())

# if __name__ == "__main__":
#     main()

# # @version(name='start')
# # @version(name='bugfix', replaces=['start'])
# # @version(name='dec', upgrades=['start'])
# # class A:

# #     @at('start')
# #     def __init__(self, counter):
# #         self.counter = counter

# #     @at('start')
# #     def inc(self):
# #         self.counter += 2

# #     @at('bugfix')
# #     def inc(self):
# #         self.counter += 1

# #     @at('dec')
# #     def dec(self):
# #         self.counter -= 1

# # @run('dec')
# # def main():
# #     ctr = A(4)
# #     ctr.inc()
# #     ctr.dec()
# #     print(ctr.counter)
