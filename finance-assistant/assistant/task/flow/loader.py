from pathlib import Path

import yaml

from assistant.task.flow.models import Flow, FlowCatalog, FlowSlot
from assistant.task.flow.steps import FlowStep

"""
这个模块作用解析yaml，封装对应对象
"""
class FlowLoader:
    def load(self,path:Path)->FlowCatalog:
        # read_text读取yaml文件内容，读取是字符串
        yaml_text = path.read_text(encoding='utf-8')
        # safe_load把读取字符串解析字典形式
        flow_dict = yaml.safe_load(yaml_text)

        # dict[str, Any]
        # flows: dict[str, Flow]
        # slots: dict[str, FlowSlot]
        # 加载所有槽位数据
        slots: dict[str, FlowSlot] = self._load_slots(flow_dict['slots'])

        # 加载所有流程数据
        # _load_flows传入所有槽位字典，为了在流程里面根据流程里面槽位名称获取槽位其他数据
        flows: dict[str, Flow] = self._load_flows(flow_dict['flows'],slots)

        return FlowCatalog(flows=flows,slots=slots)

    # 加载槽位数据
    def _load_slots(self, slots_data: dict[str,dict]) -> dict[str, FlowSlot]:
        slots:dict[str, FlowSlot] = {}
        # 遍历传入字典
        for slot_name,slot_data in slots_data.items():
            slots[slot_name] = FlowSlot(
                name=slot_name,
                **slot_data,
            )
        return slots

    # 加载所有流程数据，每个流程包含步骤数据和流程槽位数据
    def _load_flows(self, flows_data:dict[str,dict],
                      slots:dict[str, FlowSlot])->dict[str, Flow]:
        flows: dict[str, Flow] = {}
        # 遍历所有流程字典
        for flow_id,flow_data in flows_data.items():

            # 封装每个流程槽位数据
            flow_slots:list[FlowSlot] = [
                slots[step['slot_name']]
                for step in flow_data['steps']
                if step['type']=='collect'
            ]

            # 封装每个流程步骤数据
            steps:list[FlowStep] = [
                FlowStep.from_dict(step)
                for step in flow_data['steps']
            ]

            flow = Flow(
                id=flow_id,
                name=flow_data['name'],
                description=flow_data['description'],
                steps=steps,
                slots=flow_slots
            )
            flows[flow_id] = flow
        return flows


if __name__ == "__main__":
    loader = FlowLoader()
    path = Path(__file__).parents[3]/'flow_config'/'user_flows.yml'
    result = loader.load(path)
    print(result)
