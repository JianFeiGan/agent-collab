#!/usr/bin/env python3
"""
并行执行效率基准测试
测试不同并行度下的执行效率
"""

import time
import asyncio
import statistics
from typing import Dict, List, Any
from pathlib import Path
import sys
import json

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))


class ParallelExecutionTester:
    """并行执行效率测试器"""
    
    def __init__(self):
        self.results = {}
        self.project_root = project_root
    
    async def simulate_task(self, task_id: str, duration: float, cpu_bound: bool = False) -> Dict[str, Any]:
        """模拟任务执行"""
        start = time.perf_counter()
        
        if cpu_bound:
            # 模拟 CPU 密集型任务
            result = 0
            for i in range(int(duration * 1000000)):
                result += i * i
        else:
            # 模拟 I/O 密集型任务
            await asyncio.sleep(duration)
        
        end = time.perf_counter()
        
        return {
            "task_id": task_id,
            "duration_seconds": end - start,
            "expected_duration": duration,
            "overhead_seconds": (end - start) - duration,
            "success": True
        }
    
    async def run_parallel_tasks(self, task_count: int, max_parallel: int, 
                                task_duration: float = 0.1, cpu_bound: bool = False) -> Dict[str, Any]:
        """运行并行任务"""
        print(f"  🚀 运行 {task_count} 个任务，最大并行度 {max_parallel}...")
        
        # 创建任务
        tasks = []
        for i in range(task_count):
            task = self.simulate_task(
                task_id=f"task_{i}",
                duration=task_duration,
                cpu_bound=cpu_bound
            )
            tasks.append(task)
        
        # 使用信号量控制并行度
        semaphore = asyncio.Semaphore(max_parallel)
        
        async def limited_task(task):
            async with semaphore:
                return await task
        
        # 执行任务
        start = time.perf_counter()
        results = await asyncio.gather(*[limited_task(task) for task in tasks])
        end = time.perf_counter()
        
        total_time = end - start
        successful_tasks = [r for r in results if r["success"]]
        failed_tasks = [r for r in results if not r["success"]]
        
        # 计算统计信息
        durations = [r["duration_seconds"] for r in successful_tasks]
        overheads = [r["overhead_seconds"] for r in successful_tasks]
        
        return {
            "task_count": task_count,
            "max_parallel": max_parallel,
            "task_duration": task_duration,
            "cpu_bound": cpu_bound,
            "total_time_seconds": total_time,
            "successful_tasks": len(successful_tasks),
            "failed_tasks": len(failed_tasks),
            "average_task_duration": statistics.mean(durations) if durations else 0,
            "min_task_duration": min(durations) if durations else 0,
            "max_task_duration": max(durations) if durations else 0,
            "std_dev_duration": statistics.stdev(durations) if len(durations) > 1 else 0,
            "average_overhead": statistics.mean(overheads) if overheads else 0,
            "throughput_tasks_per_second": len(successful_tasks) / total_time if total_time > 0 else 0,
            "parallelism_efficiency": (task_count * task_duration) / (total_time * max_parallel) if total_time > 0 and max_parallel > 0 else 0
        }
    
    async def test_io_bound_tasks(self, task_count: int = 20, task_duration: float = 0.1) -> List[Dict[str, Any]]:
        """测试 I/O 密集型任务"""
        print(f"\n📡 测试 I/O 密集型任务 ({task_count} 个任务，每个 {task_duration}s)...")
        
        parallel_levels = [1, 2, 4, 8, 16]
        results = []
        
        for max_parallel in parallel_levels:
            if max_parallel > task_count:
                continue
            
            result = await self.run_parallel_tasks(
                task_count=task_count,
                max_parallel=max_parallel,
                task_duration=task_duration,
                cpu_bound=False
            )
            results.append(result)
            
            # 打印结果
            print(f"    并行度 {max_parallel:2d}: "
                  f"总时间 {result['total_time_seconds']:.3f}s, "
                  f"吞吐量 {result['throughput_tasks_per_second']:.1f} 任务/秒, "
                  f"效率 {result['parallelism_efficiency']:.2f}")
        
        return results
    
    async def test_cpu_bound_tasks(self, task_count: int = 10, task_duration: float = 0.05) -> List[Dict[str, Any]]:
        """测试 CPU 密集型任务"""
        print(f"\n🖥️  测试 CPU 密集型任务 ({task_count} 个任务，每个 {task_duration}s)...")
        
        parallel_levels = [1, 2, 4, 8]
        results = []
        
        for max_parallel in parallel_levels:
            if max_parallel > task_count:
                continue
            
            result = await self.run_parallel_tasks(
                task_count=task_count,
                max_parallel=max_parallel,
                task_duration=task_duration,
                cpu_bound=True
            )
            results.append(result)
            
            # 打印结果
            print(f"    并行度 {max_parallel:2d}: "
                  f"总时间 {result['total_time_seconds']:.3f}s, "
                  f"吞吐量 {result['throughput_tasks_per_second']:.1f} 任务/秒, "
                  f"效率 {result['parallelism_efficiency']:.2f}")
        
        return results
    
    async def test_mixed_tasks(self, task_count: int = 15) -> List[Dict[str, Any]]:
        """测试混合任务（I/O + CPU）"""
        print(f"\n🔀 测试混合任务 ({task_count} 个任务)...")
        
        # 创建混合任务
        tasks = []
        for i in range(task_count):
            if i % 3 == 0:
                # CPU 密集型任务
                task = self.simulate_task(
                    task_id=f"cpu_task_{i}",
                    duration=0.02,
                    cpu_bound=True
                )
            else:
                # I/O 密集型任务
                task = self.simulate_task(
                    task_id=f"io_task_{i}",
                    duration=0.1,
                    cpu_bound=False
                )
            tasks.append(task)
        
        # 使用信号量控制并行度
        semaphore = asyncio.Semaphore(4)
        
        async def limited_task(task):
            async with semaphore:
                return await task
        
        # 执行任务
        start = time.perf_counter()
        results = await asyncio.gather(*[limited_task(task) for task in tasks])
        end = time.perf_counter()
        
        total_time = end - start
        successful_tasks = [r for r in results if r["success"]]
        
        # 分析结果
        cpu_tasks = [r for r in successful_tasks if "cpu_task" in r["task_id"]]
        io_tasks = [r for r in successful_tasks if "io_task" in r["task_id"]]
        
        return [{
            "test": "mixed_tasks",
            "task_count": task_count,
            "total_time_seconds": total_time,
            "cpu_tasks": len(cpu_tasks),
            "io_tasks": len(io_tasks),
            "average_cpu_duration": statistics.mean([r["duration_seconds"] for r in cpu_tasks]) if cpu_tasks else 0,
            "average_io_duration": statistics.mean([r["duration_seconds"] for r in io_tasks]) if io_tasks else 0,
            "throughput_tasks_per_second": len(successful_tasks) / total_time if total_time > 0 else 0
        }]
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """运行所有并行执行测试"""
        print("🎯 开始并行执行效率基准测试...")
        print("=" * 60)
        
        all_results = {}
        
        # 1. I/O 密集型任务测试
        all_results["io_bound"] = await self.test_io_bound_tasks()
        
        # 2. CPU 密集型任务测试
        all_results["cpu_bound"] = await self.test_cpu_bound_tasks()
        
        # 3. 混合任务测试
        all_results["mixed"] = await self.test_mixed_tasks()
        
        print("\n" + "=" * 60)
        print("✅ 所有并行执行效率测试完成")
        
        return all_results
    
    def analyze_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """分析测试结果"""
        print("\n📊 并行执行效率分析")
        print("=" * 60)
        
        analysis = {}
        
        # 分析 I/O 密集型任务
        io_results = results.get("io_bound", [])
        if io_results:
            print("\n📡 I/O 密集型任务分析:")
            
            # 找到最佳并行度
            best_throughput = max(io_results, key=lambda x: x["throughput_tasks_per_second"])
            best_efficiency = max(io_results, key=lambda x: x["parallelism_efficiency"])
            
            print(f"  🚀 最佳吞吐量: {best_throughput['throughput_tasks_per_second']:.1f} 任务/秒 "
                  f"(并行度 {best_throughput['max_parallel']})")
            print(f"  📈 最佳效率: {best_efficiency['parallelism_efficiency']:.2f} "
                  f"(并行度 {best_efficiency['max_parallel']})")
            
            # 计算扩展性
            speedup = 1.0
            if len(io_results) >= 2:
                baseline = io_results[0]["total_time_seconds"]
                best = min(r["total_time_seconds"] for r in io_results)
                speedup = baseline / best if best > 0 else 0
                print(f"  ⚡ 加速比: {speedup:.2f}x (从 {baseline:.3f}s 到 {best:.3f}s)")
            
            analysis["io_bound"] = {
                "best_throughput": best_throughput["throughput_tasks_per_second"],
                "best_throughput_parallel": best_throughput["max_parallel"],
                "best_efficiency": best_efficiency["parallelism_efficiency"],
                "best_efficiency_parallel": best_efficiency["max_parallel"],
                "speedup": speedup
            }
        
        # 分析 CPU 密集型任务
        cpu_results = results.get("cpu_bound", [])
        if cpu_results:
            print("\n🖥️  CPU 密集型任务分析:")
            
            # 找到最佳并行度
            best_throughput = max(cpu_results, key=lambda x: x["throughput_tasks_per_second"])
            
            print(f"  🚀 最佳吞吐量: {best_throughput['throughput_tasks_per_second']:.1f} 任务/秒 "
                  f"(并行度 {best_throughput['max_parallel']})")
            
            # 计算扩展性
            speedup = 1.0
            if len(cpu_results) >= 2:
                baseline = cpu_results[0]["total_time_seconds"]
                best = min(r["total_time_seconds"] for r in cpu_results)
                speedup = baseline / best if best > 0 else 0
                print(f"  ⚡ 加速比: {speedup:.2f}x (从 {baseline:.3f}s 到 {best:.3f}s)")
            
            analysis["cpu_bound"] = {
                "best_throughput": best_throughput["throughput_tasks_per_second"],
                "best_throughput_parallel": best_throughput["max_parallel"],
                "speedup": speedup
            }
        
        # 分析混合任务
        mixed_results = results.get("mixed", [])
        if mixed_results:
            print("\n🔀 混合任务分析:")
            
            for result in mixed_results:
                print(f"  📊 总时间: {result['total_time_seconds']:.3f}s")
                print(f"  📊 吞吐量: {result['throughput_tasks_per_second']:.1f} 任务/秒")
                print(f"  📊 CPU 任务平均时间: {result['average_cpu_duration']:.3f}s")
                print(f"  📊 I/O 任务平均时间: {result['average_io_duration']:.3f}s")
            
            analysis["mixed"] = mixed_results[0] if mixed_results else {}
        
        # 总体评估
        print("\n💡 总体评估:")
        
        # I/O 密集型任务评估
        if "io_bound" in analysis:
            io_analysis = analysis["io_bound"]
            if io_analysis["best_efficiency"] > 0.8:
                print("  ✅ I/O 密集型任务并行效率优秀")
            elif io_analysis["best_efficiency"] > 0.5:
                print("  ⚠️  I/O 密集型任务并行效率良好")
            else:
                print("  ❌ I/O 密集型任务并行效率需要优化")
        
        # CPU 密集型任务评估
        if "cpu_bound" in analysis:
            cpu_analysis = analysis["cpu_bound"]
            if cpu_analysis["speedup"] > 3.0:
                print("  ✅ CPU 密集型任务扩展性优秀")
            elif cpu_analysis["speedup"] > 2.0:
                print("  ⚠️  CPU 密集型任务扩展性良好")
            else:
                print("  ❌ CPU 密集型任务扩展性需要优化")
        
        print("=" * 60)
        
        return analysis
    
    def save_results(self, results: Dict[str, Any], analysis: Dict[str, Any], output_file: str = None):
        """保存测试结果"""
        if output_file is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_path = self.project_root / "performance_results" / f"parallel_efficiency_{timestamp}.json"
        else:
            output_path = Path(output_file)
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        combined_results = {
            "test_results": results,
            "analysis": analysis,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(combined_results, f, indent=2, ensure_ascii=False)
        
        print(f"📄 测试结果已保存到: {output_path}")
        return output_path


async def main():
    """主函数"""
    tester = ParallelExecutionTester()
    
    # 运行所有测试
    results = await tester.run_all_tests()
    
    # 分析结果
    analysis = tester.analyze_results(results)
    
    # 保存结果
    tester.save_results(results, analysis)


if __name__ == "__main__":
    asyncio.run(main())