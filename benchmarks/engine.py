import filecmp
import os
import re
import random
import pprint


class Engine:
    benchmark_info = {}

    def __init__(self):
        benchmarks = ['totinfo']
        for benchmark in benchmarks:
            self.benchmark_info[benchmark] = {}
            self.benchmark_info[benchmark]["tests_info"] = []
            with open("{0}/universe.txt".format(benchmark), 'r') as f:
                test_num = 1
                for line in f.readlines():
                    if benchmark == "totinfo" or benchmark == "replace":
                        os.system(
                            "cd {0} && gcc -g -o {0} {0}.c -w -lm -Wno-return-type -fprofile-arcs -ftest-coverage".format(
                                benchmark))
                    else:
                        os.system(
                            "cd {0} && gcc -g -o {0} {0}.c -w -Wno-return-type -fprofile-arcs -ftest-coverage".format(
                                benchmark))
                    os.system("cd {0} && ./{0} {1}".format(benchmark, line))
                    os.system("cd {0} && gcov -b -c {0}".format(benchmark))
                    gcov_output = open('{0}/{0}.c.gcov'.format(benchmark), "r")
                    test_summary = self.parse(gcov_output)
                    test_summary["test_num"] = test_num
                    self.benchmark_info[benchmark]["tests_info"].append(test_summary)
                    gcov_output.close()
                    os.system("rm {0}/{0}.gcda".format(benchmark))
                    test_num += 1

        self.prioritization()
        pp = pprint.PrettyPrinter(indent=4)
        for benchmark in benchmarks:
            pp.pprint(self.benchmark_info[benchmark]["test_suites"])
            for tt in self.benchmark_info[benchmark]["test_suites"]:
                with open("{0}/{1}.txt".format(benchmark, tt), "w") as txt_file:
                    for line in self.benchmark_info[benchmark]["test_suites"][tt]:
                        txt_file.write(" ".join(line) + "\n")

        for benchmark in benchmarks:
            os.system("rm {0}/{0}".format(benchmark))
            os.system("rm {0}/{0}.gcda".format(benchmark))
            os.system("rm {0}/{0}.gcno".format(benchmark))
            os.system("rm {0}/{0}.c.gcno".format(benchmark))
            os.system("rm -rf {0}/{0}.dSYM".format(benchmark))
            t_int = 1
            while 1:
                fold_path = "{0}/v{1}".format(benchmark, t_int)
                if not os.path.isdir(fold_path):
                    break
                os.system("rm {0}/v{1}/{0}.gcda".format(benchmark, t_int))
                os.system("rm {0}/v{1}/{0}.gcno".format(benchmark, t_int))
                os.system("rm -rf {0}/v{1}/{0}.dSYM".format(benchmark, t_int))
                t_int += 1

    def parse(self, gcov_output):
        executed_stmts = re.compile(r"^\s+[0-9]+:\s+[0-9]+:.*")
        total_branches = re.compile(r"^branch\s+[0-9]+.*")
        executed_branches = re.compile(r"^branch\s+[0-9]+\s+taken\s+[1-9][0-9]*.*")
        stmt_line_num = re.compile(r"^\s+[0-9]+:\s+([0-9]+):.*")

        statements = set()
        branches = set()
        l_num = 1
        for line in gcov_output.readlines():
            if executed_stmts.match(line):
                st_num = int(stmt_line_num.match(line).group(1))
                statements.add(st_num)
            elif total_branches.match(line) and executed_branches.match(line):
                branches.add(l_num)
            l_num += 1
        test_summary = {"statement": statements, "branch": branches,
                        "statement_count": len(statements), "branch_count": len(branches)}
        return test_summary

    def select_coverage_method(self, criteria, method, benchmark):
        if method == "random":
            return self.random_coverage(criteria, benchmark)
        elif method == "total":
            return self.total_coverage(criteria, benchmark)
        elif method == "additional":
            return self.additional_coverage(criteria, benchmark)

    def prioritization(self):
        criteria_types = ['statement', 'branch']
        prioritization_methods = ['random', 'total', 'additional']
        for benchmark in self.benchmark_info:
            with open("{0}/universe.txt".format(benchmark)) as f:
                lines = f.readlines()
                lines = [line.rstrip() for line in lines]
            self.benchmark_info[benchmark]["test_suites"] = {}
            for criteria in criteria_types:
                for method in prioritization_methods:
                    test_suites = self.select_coverage_method(criteria, method, benchmark)
                    print(benchmark + "::" + criteria + "::" + method + "--->", len(test_suites))
                    self.benchmark_info[benchmark]["test_suites"][benchmark + "::" + criteria + "::" + method] = []
                    for test_suite in test_suites:
                        self.benchmark_info[benchmark]["test_suites"][benchmark + "::" + criteria + "::" + method].append(lines[test_suite['test_num'] - 1])
                    exposed_faults = self.expose_faults(benchmark, self.benchmark_info[benchmark]["test_suites"][benchmark + "::" + criteria + "::" + method])
                    print(benchmark + "::" + criteria + "::" + method + "::faults" + "--->", exposed_faults)

    def random_coverage(self, criteria, benchmark):
        random_test_cases = list(self.benchmark_info[benchmark]["tests_info"])
        random.shuffle(random_test_cases)
        return self.select_test_suites(random_test_cases, criteria)

    def total_coverage(self, criteria, benchmark):
        sorted_test_cases = []
        if criteria == "statement":
            sorted_test_cases = sorted(self.benchmark_info[benchmark]["tests_info"], key=lambda x: x['statement_count'],
                                       reverse=True)
        elif criteria == "branch":
            sorted_test_cases = sorted(self.benchmark_info[benchmark]["tests_info"], key=lambda x: x['branch_count'],
                                       reverse=True)
        return self.select_test_suites(sorted_test_cases, criteria)

    def additional_coverage(self, criteria, benchmark):
        selected_tests = []
        total_lines = set()
        covered_lines = set()

        for test_case in self.benchmark_info[benchmark]["tests_info"]:
            coverage_info = test_case[criteria]
            total_lines.update(coverage_info)

        temp_test_cases = list(self.benchmark_info[benchmark]["tests_info"])
        while len(covered_lines) < len(total_lines):
            selected_test_case = self.select_max_next_coverage(total_lines, covered_lines, temp_test_cases, criteria)
            selected_tests.append(selected_test_case)
            coverage_info = selected_test_case[criteria]
            covered_lines.update(coverage_info)
        return selected_tests

    def select_max_next_coverage(self, total, covered, test_cases, criteria):
        uncovered = total.difference(covered)
        max_code_covered = 0
        next_test_index = 0
        for index in range(len(test_cases)):
            coverage_info = test_cases[index][criteria]
            count = len(uncovered.intersection(coverage_info))
            if count > max_code_covered:
                max_code_covered = count
                next_test_index = index
        return test_cases.pop(next_test_index)

    def select_test_suites(self, test_cases, criteria):
        selected_tests = []
        total = set()
        covered = set()

        for test_case in test_cases:
            coverage_info = test_case[criteria]
            total.update(coverage_info)

        for test_case in test_cases:
            if len(covered) >= len(total):
                break
            coverage_info = test_case[criteria]
            if len(covered.union(coverage_info)) == len(covered):
                continue
            covered.update(coverage_info)
            selected_tests.append(test_case)

        return selected_tests

    def run_program(self, test_suites, benchmark, file_path, folder):
        run_file = open(file_path, 'a')
        output_str = ''
        for test_suite in test_suites:
            if benchmark == "totinfo" or benchmark == "replace":
                os.system("gcc -g -o {0}/{0} {1}/{0}.c -w -lm -Wno-return-type".format(
                    benchmark, folder))
            else:
                os.system(
                    "gcc -g -o {0}/{0} {1}/{0}.c -w -Wno-return-type".format(
                        benchmark, folder))
            output_stream = os.popen("cd {0} && ./{0} {1}".format(benchmark, test_suite))
            output = output_stream.read()
            output_str += output
            run_file.write(str(output))
            output_stream.close()
        run_file.close()
        return output_str

    def expose_faults(self, benchmark, test_suites):
        dir_pattern = re.compile(r"^v[0-9]+$")
        benchmark_path = os.path.join(benchmark)
        benchmark_run_file = "{0}/benchmark_run.txt".format(benchmark)
        faults = 0
        self.run_program(test_suites, benchmark, benchmark_run_file, benchmark)
        for subdir, dirs, files in os.walk(benchmark_path):
            for folder in dirs:
                if dir_pattern.match(folder):
                    faulty_run_file = "{0}/{1}/faulty_run.txt".format(benchmark, folder)
                    folder_path = "{0}/{1}".format(benchmark, folder)
                    self.run_program(test_suites, benchmark, faulty_run_file, folder_path)
                    if not filecmp.cmp(benchmark_run_file, faulty_run_file):
                        faults += 1
                    os.system("rm {0}/{1}/faulty_run.txt".format(benchmark, folder))
        os.system("rm {0}/benchmark_run.txt".format(benchmark))
        return faults





if __name__ == '__main__':
    engine = Engine()
