#!/usr/bin/env python3
"""
AgentCollab 性能测试脚本
测试启动速度、内存占用、并行执行效率等
"""

import time
import sys
import os
import subprocess
import psutil
import json
from pathlib import Path
from typing import Dict, List, Any
import statistics

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))


class PerformanceTester:
    """性能测试器"""
    
    def __init__(self):
        self.results = {}
        self.project_root = project_root
    
    def test_startup_time(self, iterations: int = 10) -> Dict[str, Any]:
        """测试启动时间"""
        print(f"🚀 测试启动时间 ({iterations} 次迭代)...")
        
        times = []
        for i in range(iterations):
            start = time.perf_counter()
            
            # 测试 CLI 启动
            result = subprocess.run(
                [sys.executable, "-m", "agent_collab", "--version"],
                capture_output=True,
                text=True,
                cwd=str(self.project_root)
            )
            
            end = time.perf_counter()
            times.append(end - start)
        
        avg_time = statistics.mean(times)
        std_dev = statistics.stdev(times) if len(times) > 1 else 0
        
        return {
            "test": "startup_time",
            "iterations": iterations,
            "average_seconds": avg_time,
            "std_dev_seconds": std_dev,
            "min_seconds": min(times),
            "max_seconds": max(times),
            "all_times": times
        }
    
    def test_import_time(self) -> Dict[str, Any]:
        """测试模块导入时间"""
        print("📦 测试模块导入时间...")
        
        # 测试主要模块导入
        modules = [
            "agent_collab.cli",
            "agent_collab.core.workflow",
            "agent_collab.core.scheduler",
            "agent_collab.core.executor",
            "agent_collab.agents.base",
            "agent_collab.agents.claude_code",
            "agent_collab.agents.codex",
            "agent_collab.agents.aider",
            "agent_collab.display.progress"
        ]
        
        results = {}
        for module in modules:
            start = time.perf_counter()
            try:
                __import__(module)
                end = time.perf_counter()
                results[module] = {
                    "time_seconds": end - start,
                    "status": "success"
                }
            except ImportError as e:
                results[module] = {
                    "time_seconds": 0,
                    "status": f"error: {str(e)}"
                }
        
        return {
            "test": "import_time",
            "modules": results,
            "total_time": sum(r["time_seconds"] for r in results.values() if r["status"] == "success")
        }
    
    def test_memory_usage(self) -> Dict[str, Any]:
        """测试内存使用情况"""
        print("💾 测试内存使用情况...")
        
        process = psutil.Process()
        
        # 基准内存
        baseline_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # 导入所有模块
        import agent_collab.cli
        import agent_collab.core.workflow
        import agent_collab.core.scheduler
        import agent_collab.core.executor
        import agent_collab.agents.base
        import agent_collab.agents.claude_code
        import agent_collab.agents.codex
        import agent_collab.agents.aider
        import agent_collab.display.progress
        
        # 导入后内存
        after_import_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        return {
            "test": "memory_usage",
            "baseline_mb": baseline_memory,
            "after_import_mb": after_import_memory,
            "import_overhead_mb": after_import_memory - baseline_memory
        }
    
    def test_workflow_parsing(self, workflow_file: str = None) -> Dict[str, Any]:
        """测试工作流解析性能"""
        print("⚙️ 测试工作流解析性能...")
        
        if workflow_file is None:
            # 使用示例工作流
            workflow_file = self.project_root / "examples" / "simple-workflow.yaml"
            if not workflow_file.exists():
                # 创建临时工作流
                workflow_file = self.project_root / "temp_test_workflow.yaml"
                workflow_content = """
name: test-workflow
agents:
  claude-code:
    type: claude-code
    model: claude-3-sonnet-20240229
tasks:
  - id: task1
    agent: claude-code
    prompt: "Test task 1"
  - id: task2
    agent: claude-code
    prompt: "Test task 2"
    depends_on: [task1]
  - id: task3
    agent: claude-code
    prompt: "Test task 3"
    depends_on: [task1]
"""
                workflow_file.write_text(workflow_content)
        
        # 测试解析时间
        start = time.perf_counter()
        try:
            from agent_collab.core.workflow import WorkflowParser
            config = WorkflowParser.parse(workflow_file)
            end = time.perf_counter()
            
            return {
                "test": "workflow_parsing",
                "file": str(workflow_file),
                "parse_time_seconds": end - start,
                "task_count": len(config.tasks),
                "agent_count": len(config.agents),
                "status": "success"
            }
        except Exception as e:
            return {
                "test": "workflow_parsing",
                "file": str(workflow_file),
                "parse_time_seconds": 0,
                "status": f"error: {str(e)}"
            }
    
    def test_scheduler_performance(self, task_count: int = 100) -> Dict[str, Any]:
        """测试调度器性能"""
        print(f"📊 测试调度器性能 ({task_count} 个任务)...")
        
        from agent_collab.core.workflow import TaskConfig
        from agent_collab.core.scheduler import TaskScheduler
        
        # 创建测试任务
        tasks = []
        for i in range(task_count):
            task = TaskConfig(
                id=f"task_{i}",
                agent="test-agent",
                prompt=f"Test task {i}",
                depends_on=[f"task_{i-1}"] if i > 0 else []
            )
            tasks.append(task)
        
        # 测试调度时间
        start = time.perf_counter()
        scheduler = TaskScheduler(tasks)
        levels = scheduler.get_execution_order()
        end = time.perf_counter()
        
        return {
            "test": "scheduler_performance",
            "task_count": task_count,
            "schedule_time_seconds": end - start,
            "execution_levels": len(levels),
            "parallelizable_tasks": sum(len(level) for level in levels if len(level) > 1)
        }
    
    def run_all_tests(self) -> Dict[str, Any]:
        """运行所有性能测试"""
        print("🎯 开始 AgentCollab 性能测试...")
        print("=" * 50)
        
        results = {}
        
        # 1. 启动时间测试
        results["startup_time"] = self.test_startup_time()
        
        # 2. 导入时间测试
        results["import_time"] = self.test_import_time()
        
        # 3. 内存使用测试
        results["memory_usage"] = self.test_memory_usage()
        
        # 4. 工作流解析测试
        results["workflow_parsing"] = self.test_workflow_parsing()
        
        # 5. 调度器性能测试
        results["scheduler_performance"] = self.test_scheduler_performance()
        
        print("=" * 50)
        print("✅ 所有性能测试完成")
        
        return results
    
    def save_results(self, results: Dict[str, Any], output_file: str = None):
        """保存测试结果"""
        if output_file is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_path = self.project_root / "performance_results" / f"perf_test_{timestamp}.json"
        else:
            output_path = Path(output_file)
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"📄 测试结果已保存到: {output_path}")
        return output_path
    
    def print_summary(self, results: Dict[str, Any]):
        """打印测试摘要"""
        print("\n📊 性能测试摘要")
        print("=" * 50)
        
        # 启动时间
        startup = results.get("startup_time", {})
        print(f"🚀 启动时间: {startup.get('average_seconds', 0):.3f}s (±{startup.get('std_dev_seconds', 0):.3f}s)")
        
        # 导入时间
        import_time = results.get("import_time", {})
        print(f"📦 总导入时间: {import_time.get('total_time', 0):.3f}s")
        
        # 内存使用
        memory = results.get("memory_usage", {})
        print(f"💾 内存占用: {memory.get('after_import_mb', 0):.1f}MB (导入开销: {memory.get('import_overhead_mb', 0):.1f}MB)")
        
        # 工作流解析
        parsing = results.get("workflow_parsing", {})
        print(f"⚙️ 工作流解析: {parsing.get('parse_time_seconds', 0):.3f}s")
        
        # 调度器性能
        scheduler = results.get("scheduler_performance", {})
        print(f"📊 调度器性能: {scheduler.get('schedule_time_seconds', 0):.3f}s ({scheduler.get('task_count', 0)} 任务)")
        
        print("=" * 50)


def main():
    """主函数"""
    tester = PerformanceTester()
    
    # 运行所有测试
    results = tester.run_all_tests()
    
    # 打印摘要
    tester.print_summary(results)
    
    # 保存结果
    output_file = tester.save_results(results)
    
    # 生成优化建议
    print("\n💡 优化建议")
    print("=" * 50)
    
    startup_time = results.get("startup_time", {}).get("average_seconds", 0)
    if startup_time > 1.0:
        print("⚠️  启动时间较长，建议:")
        print("   1. 使用延迟导入减少初始加载")
        print("   2. 优化 CLI 入口点")
        print("   3. 考虑使用缓存机制")
    
    import_time = results.get("import_time", {}).get("total_time", 0)
    if import_time > 0.5:
        print("⚠️  导入时间较长，建议:")
        print("   1. 检查是否有不必要的导入")
        print("   2. 使用延迟导入策略")
        print("   3. 优化模块依赖关系")
    
    memory_overhead = results.get("memory_usage", {}).get("import_overhead_mb", 0)
    if memory_overhead > 50:
        print("⚠️  内存开销较大，建议:")
        print("   1. 检查是否有内存泄漏")
        print("   2. 优化数据结构")
        print("   3. 使用生成器替代列表")
    
    print("=" * 50)


if __name__ == "__main__":
    main()