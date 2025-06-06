# Interactive Feedback MCP
# Developed by Fábio Ferreira (https://x.com/fabiomlferreira)
# Inspired by/related to dotcursorrules.com (https://dotcursorrules.com/)
# Enhanced by Pau Oliva (https://x.com/pof) with ideas from https://github.com/ttommyth/interactive-mcp
import os
import sys
import json
import tempfile
import subprocess
import shutil
from pathlib import Path

from typing import Annotated, Dict, List, Optional, Any

from fastmcp import FastMCP
from pydantic import Field

# The log_level is necessary for Cline to work: https://github.com/jlowin/fastmcp/issues/81
mcp = FastMCP("Interactive Feedback MCP", log_level="ERROR")

# 确保附件目录存在
script_dir = os.path.dirname(os.path.abspath(__file__))
attachments_dir = os.path.join(script_dir, "attachments")
os.makedirs(attachments_dir, exist_ok=True)

# 临时文件清理
def cleanup_temp_files():
    """清理临时目录中的过期文件"""
    temp_dir = os.path.join(os.path.expanduser("~"), ".interactive_feedback_temp")
    if os.path.exists(temp_dir):
        try:
            # 删除7天前的临时文件
            import time
            current_time = time.time()
            for item in os.listdir(temp_dir):
                item_path = os.path.join(temp_dir, item)
                if os.path.isfile(item_path):
                    # 获取文件修改时间
                    file_time = os.path.getmtime(item_path)
                    # 如果文件超过7天未修改，删除它
                    if current_time - file_time > 7 * 86400:  # 7天的秒数
                        os.remove(item_path)
        except Exception as e:
            print(f"清理临时文件时出错: {e}")

# 启动时清理临时文件
cleanup_temp_files()

def launch_feedback_ui(summary: str, predefinedOptions: list[str] | None = None) -> dict[str, Any]:
    # Create a temporary file for the feedback result
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        output_file = tmp.name

    try:
        # Get the path to feedback_ui.py relative to this script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        feedback_ui_path = os.path.join(script_dir, "feedback_ui.py")

        # Run feedback_ui.py as a separate process
        # NOTE: There appears to be a bug in uv, so we need
        # to pass a bunch of special flags to make this work
        args = [
            sys.executable,
            "-u",
            feedback_ui_path,
            "--prompt", summary,
            "--output-file", output_file,
            "--predefined-options", "|||".join(predefinedOptions) if predefinedOptions else ""
        ]
        result = subprocess.run(
            args,
            check=False,
            shell=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            close_fds=True
        )
        if result.returncode != 0:
            raise Exception(f"Failed to launch feedback UI: {result.returncode}")

        # Read the result from the temporary file
        with open(output_file, 'r') as f:
            result = json.load(f)
        os.unlink(output_file)
        
        # 处理附件数据
        if "attachments" in result and result["attachments"]:
            # 创建会话特定的附件目录
            session_id = os.urandom(4).hex()
            attachment_dir = os.path.join(script_dir, "attachments", session_id)
            os.makedirs(attachment_dir, exist_ok=True)
            
            # 处理每个附件
            processed_attachments = []
            for attachment in result["attachments"]:
                if os.path.exists(attachment["path"]):
                    # 复制文件到附件目录
                    dest_path = os.path.join(attachment_dir, attachment["name"])
                    shutil.copy2(attachment["path"], dest_path)
                    
                    # 更新附件信息
                    attachment_info = {
                        "name": attachment["name"],
                        "type": attachment["type"],
                        "size": attachment["size"],
                    }
                    
                    # 如果是图片且有base64数据，保留它
                    if attachment["type"] == "image" and "data" in attachment:
                        attachment_info["data"] = attachment["data"]
                    
                    processed_attachments.append(attachment_info)
            
            # 更新结果中的附件数据
            result["attachments"] = processed_attachments
        
        return result
    except Exception as e:
        if os.path.exists(output_file):
            os.unlink(output_file)
        raise e

@mcp.tool()
def interactive_feedback(
    message: str = Field(description="The specific question for the user"),
    predefined_options: list = Field(default=None, description="Predefined options for the user to choose from (optional)"),
) -> Dict[str, Any]:
    """Request interactive feedback from the user"""
    predefined_options_list = predefined_options if isinstance(predefined_options, list) else None
    return launch_feedback_ui(message, predefined_options_list)

if __name__ == "__main__":
    mcp.run(transport="stdio")
