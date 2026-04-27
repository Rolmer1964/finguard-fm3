from uuid import uuid4

from handlers.action_shift_ai.main import main


def run(metadata):
    module_inputs = metadata.inputs.get('module_inputs', {})
    conversation_id = metadata.inputs.get("var", dict()).get("STK_WORKFLOW_EXECUTION_ID", str(uuid4()))
    main(module_inputs=module_inputs, conversation_id=conversation_id)
