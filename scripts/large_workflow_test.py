#!/usr/bin/env python3
"""
大型工作流性能测试
测试50+任务的工作流解析、调度和执行性能
"""

import time
import sys
import yaml
import statistics
from pathlib import Path
from typing import Dict, List, Any
import random

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))


class LargeWorkflowTester:
    """大型工作流性能测试器"""
    
    def __init__(self):
        self.results = {}
        self.project_root = project_root
    
    def generate_large_workflow(self, task_count: int = 50, dependency_density: float = 0.3) -> Dict[str, Any]:
        """生成大型工作流配置"""
        print(f"🔧 生成大型工作流 ({task_count} 任务, 依赖密度 {dependency_density})...")
        
        agents = {
            "claude-code": {
                "type": "claude-code",
                "model": "claude-3-sonnet-20240229"
            },
            "codex": {
                "type": "codex",
                "model": "code-davinci-002"
            },
            "aider": {
                "type": "aider",
                "model": "gpt-4"
            }
        }
        
        tasks = []
        task_ids = [f"task_{i}" for i in range(task_count)]
        
        for i, task_id in enumerate(task_ids):
            # 随机选择 Agent
            agent = random.choice(list(agents.keys()))
            
            # 随机生成依赖关系（确保无环）
            depends_on = []
            if i > 0 and random.random() < dependency_density:
                # 只依赖前面的任务，避免循环
                possible_deps = task_ids[:i]
                dep_count = min(random.randint(1, 3), len(possible_deps))
                depends_on = random.sample(possible_deps, dep_count)
            
            task = {
                "id": task_id,
                "agent": agent,
                "prompt": f"执行任务 {task_id}，这是第 {i+1} 个任务。"
                          f"任务内容：处理数据并生成报告。"
                          f"输入文件：data/input_{task_id}.csv"
                          f"输出文件：output/report_{task_id}.md",
                "depends_on": depends_on
            }
            tasks.append(task)
        
        workflow = {
            "name": f"large-workflow-{task_count}",
            "agents": agents,
            "tasks": tasks,
            "strategy": {
                "max_parallel": 4,
                "timeout": 300
            }
        }
        
        return workflow
    
    def test_workflow_parsing(self, workflow_config: Dict[str, Any]) -> Dict[str, Any]:
        """测试工作流解析性能"""
        print("⚙️ 测试工作流解析性能...")
        
        # 保存为临时文件
        temp_file = self.project_root / "temp_large_workflow.yaml"
        with open(temp_file, 'w', encoding='utf-8') as f:
            yaml.dump(workflow_config, f, default_flow_style=False)
        
        # 测试解析时间
        from agent_collab.core.workflow import WorkflowParser
        
        parse_times = []
        for _ in range(5):  # 多次测试取平均
            start = time.perf_counter()
            try:
                config = WorkflowParser.parse(temp_file)
                end = time.perf_counter()
                parse_times.append(end - start)
            except Exception as e:
                print(f"❌ 解析失败: {e}")
                return {
                    "test": "workflow_parsing",
                    "status": f"error: {str(e)}",
                    "task_count": len(workflow_config.get("tasks", []))
                }
        
        avg_parse_time = statistics.mean(parse_times)
        
        # 清理临时文件
        temp_file.unlink(missing_ok=True)
        
        return {
            "test": "workflow_parsing",
            "task_count": len(workflow_config.get("tasks", [])),
            "average_parse_time_seconds": avg_parse_time,
            "min_parse_time_seconds": min(parse_times),
            "max_parse_time_seconds": max(parse_times),
            "std_dev_seconds": statistics.stdev(parse_times) if len(parse_times) > 1 else 0,
            "status": "success"
        }
    
    def test_scheduler_performance(self, workflow_config: Dict[str, Any]) -> Dict[str, Any]:
        """测试调度器性能"""
        print("📊 测试调度器性能...")
        
        from agent_collab.core.workflow import WorkflowParser, TaskConfig
        from agent_collab.core.scheduler import TaskScheduler
        
        # 解析工作流
        temp_file = self.project_root / "temp_large_workflow.yaml"
        with open(temp_file, 'w', encoding='utf-8') as f:
            yaml.dump(workflow_config, f, default_flow_style=False)
        
        try:
            config = WorkflowParser.parse(temp_file)
        except Exception as e:
            print(f"❌ 解析失败: {e}")
            return {
                "test": "scheduler_performance",
                "status": f"error: {str(e)}",
                "task_count": len(workflow_config.get("tasks", []))
            }
        
        # 测试调度时间
        schedule_times = []
        levels = []
        for _ in range(5):
            start = time.perf_counter()
            try:
                scheduler = TaskScheduler(config.tasks)
                levels = scheduler.get_execution_order()
                end = time.perf_counter()
                schedule_times.append(end - start)
            except Exception as e:
                print(f"❌ 调度失败: {e}")
                return {
                    "test": "scheduler_performance",
                    "status": f"error: {str(e)}",
                    "task_count": len(config.tasks)
                }
        
        avg_schedule_time = statistics.mean(schedule_times)
        
        # 计算并行度
        parallelizable_tasks = sum(len(level) for level in levels if len(level) > 1)
        max_parallelism = max(len(level) for level in levels) if levels else 0
        
        # 清理临时文件
        temp_file.unlink(missing_ok=True)
        
        return {
            "test": "scheduler_performance",
            "task_count": len(config.tasks),
            "average_schedule_time_seconds": avg_schedule_time,
            "min_schedule_time_seconds": min(schedule_times),
            "max_schedule_time_seconds": max(schedule_times),
            "std_dev_seconds": statistics.stdev(schedule_times) if len(schedule_times) > 1 else 0,
            "execution_levels": len(levels),
            "parallelizable_tasks": parallelizable_tasks,
            "max_parallelism": max_parallelism,
            "status": "success"
        }
    
    def test_memory_usage(self, workflow_config: Dict[str, Any]) -> Dict[str, Any]:
        """测试内存使用情况"""
        print("💾 测试内存使用情况...")
        
        try:
            import psutil
            process = psutil.Process()
            
            # 基准内存
            baseline_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # 解析大型工作流
            from agent_collab.core.workflow import WorkflowParser
            
            temp_file = self.project_root / "temp_large_workflow.yaml"
            with open(temp_file, 'w', encoding='utf-8') as f:
                yaml.dump(workflow_config, f, default_flow_style=False)
            
            config = WorkflowParser.parse(temp_file)
            
            # 解析后内存
            after_parse_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # 创建调度器
            from agent_collab.core.scheduler import TaskScheduler
            scheduler = TaskScheduler(config.tasks)
            levels = scheduler.get_execution_order()
            
            # 调度后内存
            after_schedule_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # 清理临时文件
            temp_file.unlink(missing_ok=True)
            
            return {
                "test": "memory_usage",
                "baseline_mb": baseline_memory,
                "after_parse_mb": after_parse_memory,
                "after_schedule_mb": after_schedule_memory,
                "parse_overhead_mb": after_parse_memory - baseline_memory,
                "schedule_overhead_mb": after_schedule_memory - after_parse_memory,
                "total_overhead_mb": after_schedule_memory - baseline_memory,
                "task_count": len(config.tasks),
                "status": "success"
            }
        except ImportError:
            print("⚠️  psutil 未安装，跳过内存测试")
            return {
                "test": "memory_usage",
                "status": "skipped: psutil not installed",
                "task_count": len(workflow_config.get("tasks", []))
            }
    
    def run_performance_tests(self, task_counts: List[int] = None) -> Dict[str, Any]:
        """运行性能测试"""
        if task_counts is None:
            task_counts = [10, 25, 50, 100]
        
        print("🎯 开始大型工作流性能测试...")
        print("=" * 60)
        
        all_results = {}
        
        for task_count in task_counts:
            print(f"\n📋 测试 {task_count} 个任务的工作流...")
            print("-" * 40)
            
            # 生成工作流
            workflow_config = self.generate_large_workflow(task_count)
            
            # 测试解析性能
            parse_result = self.test_workflow_parsing(workflow_config)
            
            # 测试调度性能
            schedule_result = self.test_scheduler_performance(workflow_config)
            
            # 测试内存使用
            memory_result = self.test_memory_usage(workflow_config)
            
            all_results[f"tasks_{task_count}"] = {
                "task_count": task_count,
                "parsing": parse_result,
                "scheduling": schedule_result,
                "memory": memory_result
            }
            
            # 打印当前测试结果
            self.print_task_count_summary(task_count, parse_result, schedule_result, memory_result)
        
        print("\n" + "=" * 60)
        print("✅ 所有大型工作流性能测试完成")
        
        return all_results
    
    def print_task_count_summary(self, task_count: int, parse_result: Dict, schedule_result: Dict, memory_result: Dict):
        """打印单个任务数量的测试摘要"""
        print(f"\n📊 {task_count} 任务性能摘要:")
        
        # 解析性能
        if parse_result.get("status") == "success":
            parse_time = parse_result.get("average_parse_time_seconds", 0)
            print(f"  ⚙️ 解析时间: {parse_time:.4f}s")
        
        # 调度性能
        if schedule_result.get("status") == "success":
            schedule_time = schedule_result.get("average_schedule_time_seconds", 0)
            levels = schedule_result.get("execution_levels", 0)
            max_parallel = schedule_result.get("max_parallelism", 0)
            print(f"  📊 调度时间: {schedule_time:.4f}s")
            print(f"  📊 执行层级: {levels}")
            print(f"  📊 最大并行度: {max_parallel}")
        
        # 内存使用
        if memory_result.get("status") == "success":
            total_overhead = memory_result.get("total_overhead_mb", 0)
            print(f"  💾 内存开销: {total_overhead:.2f}MB")
    
    def print_comprehensive_summary(self, results: Dict[str, Any]):
        """打印综合测试摘要"""
        print("\n" + "=" * 60)
        print("📊 大型工作流性能测试综合摘要")
        print("=" * 60)
        
        # 收集所有数据
        parse_times = []
        schedule_times = []
        memory_overheads = []
        task_counts = []
        
        for key, result in results.items():
            if key.startswith("tasks_"):
                task_count = result.get("task_count", 0)
                task_counts.append(task_count)
                
                parse_result = result.get("parsing", {})
                if parse_result.get("status") == "success":
                    parse_times.append(parse_result.get("average_parse_time_seconds", 0))
                
                schedule_result = result.get("scheduling", {})
                if schedule_result.get("status") == "success":
                    schedule_times.append(schedule_result.get("average_schedule_time_seconds", 0))
                
                memory_result = result.get("memory", {})
                if memory_result.get("status") == "success":
                    memory_overheads.append(memory_result.get("total_overhead_mb", 0))
        
        # 打印汇总
        if task_counts:
            print(f"📋 测试任务数量: {', '.join(map(str, sorted(task_counts)))}")
        
        if parse_times:
            print(f"⚙️ 平均解析时间: {statistics.mean(parse_times):.4f}s")
            print(f"  最小: {min(parse_times):.4f}s, 最大: {max(parse_times):.4f}s")
        
        if schedule_times:
            print(f"📊 平均调度时间: {statistics.mean(schedule_times):.4f}s")
            print(f"  最小: {min(schedule_times):.4f}s, 最大: {max(schedule_times):.4f}s")
        
        if memory_overheads:
            print(f"💾 平均内存开销: {statistics.mean(memory_overheads):.2f}MB")
            print(f"  最小: {min(memory_overheads):.2f}MB, 最大: {max(memory_overheads):.2f}MB")
        
        # 性能评估
        print("\n💡 性能评估:")
        
        # 解析性能评估
        if parse_times:
            avg_parse = statistics.mean(parse_times)
            if avg_parse < 0.1:
                print("  ✅ 解析性能优秀 (< 0.1s)")
            elif avg_parse < 0.5:
                print("  ⚠️  解析性能良好 (0.1s - 0.5s)")
            else:
                print("  ❌ 解析性能需要优化 (> 0.5s)")
        
        # 调度性能评估
        if schedule_times:
            avg_schedule = statistics.mean(schedule_times)
            if avg_schedule < 0.01:
                print("  ✅ 调度性能优秀 (< 0.01s)")
            elif avg_schedule < 0.1:
                print("  ⚠️  调度性能良好 (0.01s - 0.1s)")
            else:
                print("  ❌ 调度性能需要优化 (> 0.1s)")
        
        # 内存性能评估
        if memory_overheads:
            avg_memory = statistics.mean(memory_overheads)
            if avg_memory < 10:
                print("  ✅ 内存开销优秀 (< 10MB)")
            elif avg_memory < 50:
                print("  ⚠️  内存开销良好 (10MB - 50MB)")
            else:
                print("  ❌ 内存开销需要优化 (> 50MB)")
        
        print("=" * 60)
    
    def save_results(self, results: Dict[str, Any], output_file: str = None):
        """保存测试结果"""
        if output_file is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_path = self.project_root / "performance_results" / f"large_workflow_perf_{timestamp}.json"
        else:
            output_path = Path(output_file)
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        import json
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"📄 测试结果已保存到: {output_path}")
        return output_path


def main():
    """主函数"""
    tester = LargeWorkflowTester()
    
    # 运行性能测试
    results = tester.run_performance_tests([10, 25, 50, 100])
    
    # 打印综合摘要
    tester.print_comprehensive_summary(results)
    
    # 保存结果
    tester.save_results(results)


if __name__ == "__main__":
    main()