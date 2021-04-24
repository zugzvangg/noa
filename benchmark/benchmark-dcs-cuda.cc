#include "noa-bench.hh"

#include <noa/pms/dcs_cuda.hh>
#include <noa/pms/constants.hh>

#include <benchmark/benchmark.h>

using namespace noa::pms;

BENCHMARK_F(DCSBenchmark, BremsstrahlungVectorisedCPU)
(benchmark::State &state) {
    const auto kinetic_energies = DCSData::get_kinetic_energies();
    const auto recoil_energies = DCSData::get_recoil_energies();
    auto result = torch::zeros_like(kinetic_energies);
    const auto element = STANDARD_ROCK;
    const auto mu = MUON_MASS;
    for (auto _ : state)
        bremsstrahlung_cpu(result, kinetic_energies, recoil_energies, element, mu);
}

BENCHMARK_F(DCSBenchmark, BremsstrahlungVectorisedCPU32)
(benchmark::State &state) {
    const auto kinetic_energies = DCSData::get_kinetic_energies().to(torch::dtype(torch::kFloat32));
    const auto recoil_energies = DCSData::get_recoil_energies().to(torch::dtype(torch::kFloat32));
    auto result = torch::zeros_like(kinetic_energies);
    const auto element = STANDARD_ROCK;
    const auto mu = MUON_MASS;
    for (auto _ : state)
        bremsstrahlung_cpu(result, kinetic_energies, recoil_energies, element, mu);
}

BENCHMARK_F(DCSBenchmark, BremsstrahlungVectorisedCUDA)
(benchmark::State &state) {
    const auto kinetic_energies = DCSData::get_kinetic_energies().to(torch::kCUDA);
    const auto recoil_energies = DCSData::get_recoil_energies().to(torch::kCUDA);
    auto result = torch::zeros_like(kinetic_energies);
    const auto element = STANDARD_ROCK;
    const auto mu = MUON_MASS;
    for (auto _ : state)
        bremsstrahlung_cuda(result, kinetic_energies, recoil_energies, element, mu);
}

BENCHMARK_F(DCSBenchmark, BremsstrahlungVectorisedCUDA32)
(benchmark::State &state) {
    const auto kinetic_energies = DCSData::get_kinetic_energies().to(torch::dtype(torch::kFloat32).device(torch::kCUDA));
    const auto recoil_energies = DCSData::get_recoil_energies().to(torch::dtype(torch::kFloat32).device(torch::kCUDA));
    auto result = torch::zeros_like(kinetic_energies);
    const auto element = STANDARD_ROCK;
    const auto mu = MUON_MASS;
    for (auto _ : state)
        bremsstrahlung_cuda(result, kinetic_energies, recoil_energies, element, mu);
}