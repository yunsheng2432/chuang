class ErNiao:
    def __init__(self, name):
        self.name = name

    def find_son(self):
        print(f"{self.name} 的好大儿是滑滑头！")

class HuaTou(ErNiao):
    def __init__(self, name):
        super().__init__(name)

    def find_father(self):
        print(f"{self.name} 的父亲是二鸟！")

    def find_son(self):
        print(f"{self.name} 的儿子是二鸟的孙子！")


erniao = ErNiao("二鸟")
huatou = HuaTou("滑滑头")

erniao.find_son()
huatou.find_father()
huatou.find_son()